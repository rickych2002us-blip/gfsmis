import os
import uuid
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
    send_from_directory,
    abort,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, Station, REGIONS

# ─── Import all models ───
from models import (
    FireCertificate,
    CertificateDocument,
    BuildingPlan,
    FireInspection,
    InspectionPhoto,
    InspectionChecklistItem,
    Violation,
    Incident,
    IncidentResource,
    IncidentResponder,
    Investigation,
    Evidence,
    WitnessStatement,
    PublicComplaint,
    HazardReport,
    TrainingRegistration,
    LeaveRequest,
    Attendance,
    PerformanceEvaluation,
    Course,
    CourseEnrollment,
    Exam,
    ExamResult,
    Certification,
    Vehicle,
    MaintenanceRecord,
    FuelLog,
    Asset,
    Procurement,
    FeeCollection,
    Budget,
    FinancialTransaction,
    Document,
    DutyRoster,
    OccurrenceLog,
    DisasterEvent,
    DisasterDeployment,
    Shelter,
    Hydrant,
    RiskZone,
    AuditLog,
)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

with app.app_context():
    db.create_all()

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "info"


@app.context_processor
def inject_globals():
    return dict(REGIONS=REGIONS)


# ─── Helpers ───

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash("Access denied. Insufficient permissions.", "danger")
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def log_action(user_id, action, module, description=None, ip_address=None):
    log = AuditLog(
        user_id=user_id,
        action=action,
        module=module,
        description=description,
        ip_address=ip_address or request.remote_addr,
    )
    db.session.add(log)
    db.session.commit()


def allowed_file(filename, exts=None):
    if exts is None:
        exts = {"pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "xls", "xlsx"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts


def save_file(file, subdir=""):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit(".", 1)[1].lower()
        filename = f"{uuid.uuid4().hex}.{ext}"
        upload_dir = os.path.join(app.config["UPLOAD_FOLDER"], subdir)
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)
        return filename, filepath
    return None, None


def get_dashboard_stats():
    return {
        "active_incidents": Incident.query.filter(
            Incident.status.in_(["reported", "dispatched", "active"])
        ).count(),
        "pending_certificates": FireCertificate.query.filter_by(status="pending").count(),
        "scheduled_inspections": FireInspection.query.filter_by(status="scheduled").count(),
        "total_staff": User.query.filter_by(is_active=True).count(),
        "vehicles_available": Vehicle.query.filter_by(status="available").count(),
        "pending_complaints": PublicComplaint.query.filter_by(status="submitted").count(),
        "open_investigations": Investigation.query.filter_by(status="open").count(),
        "revenue_month": db.session.query(db.func.sum(FeeCollection.amount)).filter(
            db.extract("month", FeeCollection.collected_at) == datetime.utcnow().month,
            FeeCollection.status == "paid",
        ).scalar() or 0,
    }


# ─── Auth ───

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=request.form.get("remember"))
            user.last_login = datetime.utcnow()
            db.session.commit()
            log_action(user.id, "login", "auth", f"User {user.username} logged in")
            flash(f"Welcome back, {user.first_name}!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    log_action(current_user.id, "logout", "auth", f"User {current_user.username} logged out")
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/profile")
@login_required
def profile():
    return render_template("profile.html")


@app.route("/profile/update", methods=["POST"])
@login_required
def profile_update():
    user = current_user
    user.first_name = request.form.get("first_name", user.first_name)
    user.last_name = request.form.get("last_name", user.last_name)
    user.phone = request.form.get("phone", user.phone)
    user.email = request.form.get("email", user.email)
    if request.form.get("password"):
        user.set_password(request.form["password"])
    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("profile"))


# ─── Dashboard ───

@app.route("/dashboard")
@login_required
def dashboard():
    stats = get_dashboard_stats()
    recent_incidents = Incident.query.order_by(Incident.created_at.desc()).limit(5).all()
    recent_certs = FireCertificate.query.order_by(FireCertificate.created_at.desc()).limit(5).all()
    return render_template("dashboard.html", stats=stats, recent_incidents=recent_incidents, recent_certs=recent_certs)


# ────────────────────────────────────────────────────────────
# MODULE 1: FIRE PREVENTION & COMPLIANCE MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/fire-prevention")
@login_required
def fire_prevention_dashboard():
    stats = {
        "total": FireCertificate.query.count(),
        "pending": FireCertificate.query.filter_by(status="pending").count(),
        "approved": FireCertificate.query.filter_by(status="approved").count(),
        "rejected": FireCertificate.query.filter_by(status="rejected").count(),
        "plans": BuildingPlan.query.count(),
    }
    certificates = FireCertificate.query.order_by(FireCertificate.created_at.desc()).all()
    plans = BuildingPlan.query.order_by(BuildingPlan.submitted_at.desc()).all()
    return render_template("modules/fire_prevention/dashboard.html", stats=stats, certificates=certificates, plans=plans)


@app.route("/fire-prevention/certificates/new", methods=["GET", "POST"])
@login_required
def certificate_new():
    if request.method == "POST":
        cert = FireCertificate(
            certificate_no=f"FC-{uuid.uuid4().hex[:8].upper()}",
            applicant_name=request.form["applicant_name"],
            applicant_email=request.form.get("applicant_email"),
            applicant_phone=request.form.get("applicant_phone"),
            business_name=request.form.get("business_name"),
            business_address=request.form.get("business_address"),
            property_type=request.form.get("property_type"),
            submitted_by=current_user.id,
        )
        db.session.add(cert)
        db.session.commit()
        log_action(current_user.id, "create", "fire_prevention", f"Certificate {cert.certificate_no} created")
        flash("Certificate application submitted successfully.", "success")
        return redirect(url_for("fire_prevention_dashboard"))
    return render_template("modules/fire_prevention/certificate_form.html")


@app.route("/fire-prevention/certificates/<int:id>")
@login_required
def certificate_view(id):
    cert = FireCertificate.query.get_or_404(id)
    return render_template("modules/fire_prevention/certificate_view.html", cert=cert)


@app.route("/fire-prevention/certificates/<int:id>/status", methods=["POST"])
@login_required
@role_required("admin", "inspector", "supervisor")
def certificate_update_status(id):
    cert = FireCertificate.query.get_or_404(id)
    cert.status = request.form["status"]
    cert.inspected_by = current_user.id
    if request.form["status"] == "approved":
        cert.issue_date = date.today()
    cert.remarks = request.form.get("remarks")
    db.session.commit()
    log_action(current_user.id, "update_status", "fire_prevention",
               f"Certificate {cert.certificate_no} -> {cert.status}")
    flash(f"Certificate status updated to {cert.status}.", "success")
    return redirect(url_for("certificate_view", id=id))


@app.route("/fire-prevention/plans/new", methods=["GET", "POST"])
@login_required
def building_plan_new():
    if request.method == "POST":
        plan = BuildingPlan(
            project_name=request.form["project_name"],
            applicant_name=request.form["applicant_name"],
            applicant_email=request.form.get("applicant_email"),
            address=request.form.get("address"),
        )
        file, path = save_file(request.files.get("plan_file"), "building_plans")
        if file:
            plan.plan_file = path
        db.session.add(plan)
        db.session.commit()
        flash("Building plan submitted successfully.", "success")
        return redirect(url_for("fire_prevention_dashboard"))
    return render_template("modules/fire_prevention/plan_form.html")


# ────────────────────────────────────────────────────────────
# MODULE 2: FIRE INSPECTION MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/inspections")
@login_required
def inspection_dashboard():
    stats = {
        "total": FireInspection.query.count(),
        "scheduled": FireInspection.query.filter_by(status="scheduled").count(),
        "completed": FireInspection.query.filter_by(status="completed").count(),
    }
    inspections = FireInspection.query.order_by(FireInspection.created_at.desc()).all()
    return render_template("modules/inspection/dashboard.html", stats=stats, inspections=inspections)


@app.route("/inspections/new", methods=["GET", "POST"])
@login_required
def inspection_new():
    inspectors = User.query.filter(User.role.in_(["inspector", "admin", "supervisor"])).all()
    if request.method == "POST":
        insp = FireInspection(
            inspection_no=f"INSP-{uuid.uuid4().hex[:8].upper()}",
            property_name=request.form["property_name"],
            property_address=request.form.get("property_address"),
            property_type=request.form.get("property_type"),
            region=request.form.get("region"),
            photo=None,
            inspection_type=request.form.get("inspection_type"),
            inspector_id=request.form.get("inspector_id"),
            scheduled_date=datetime.strptime(request.form["scheduled_date"], "%Y-%m-%dT%H:%M"),
        )
        file, path = save_file(request.files.get("photo"), "inspection_photos")
        if file:
            insp.photo = path
        db.session.add(insp)
        db.session.commit()
        log_action(current_user.id, "create", "inspection", f"Inspection {insp.inspection_no} created")
        flash("Inspection scheduled successfully.", "success")
        return redirect(url_for("inspection_dashboard"))
    return render_template("modules/inspection/inspection_form.html", inspectors=inspectors)


@app.route("/inspections/<int:id>")
@login_required
def inspection_view(id):
    insp = FireInspection.query.get_or_404(id)
    return render_template("modules/inspection/inspection_view.html", insp=insp)


@app.route("/inspections/<int:id>/conduct", methods=["POST"])
@login_required
def inspection_conduct(id):
    insp = FireInspection.query.get_or_404(id)
    insp.conducted_date = datetime.utcnow()
    insp.findings = request.form.get("findings")
    insp.recommendations = request.form.get("recommendations")
    insp.compliance_status = request.form.get("compliance_status")
    insp.follow_up_required = "follow_up_required" in request.form
    if insp.follow_up_required and request.form.get("follow_up_date"):
        insp.follow_up_date = datetime.strptime(request.form["follow_up_date"], "%Y-%m-%d").date()
    insp.status = "completed"
    db.session.commit()
    log_action(current_user.id, "conduct", "inspection", f"Inspection {insp.inspection_no} completed")
    flash("Inspection completed and recorded.", "success")
    return redirect(url_for("inspection_view", id=id))


@app.route("/inspections/<int:id>/checklist", methods=["POST"])
@login_required
def inspection_checklist_add(id):
    insp = FireInspection.query.get_or_404(id)
    item = InspectionChecklistItem(
        inspection_id=id,
        item_name=request.form["item_name"],
        is_compliant="is_compliant" in request.form,
        remarks=request.form.get("remarks"),
    )
    db.session.add(item)
    db.session.commit()
    return redirect(url_for("inspection_view", id=id))


@app.route("/inspections/<int:id>/violation", methods=["POST"])
@login_required
def inspection_violation_add(id):
    v = Violation(
        inspection_id=id,
        violation_code=request.form.get("violation_code"),
        description=request.form["description"],
        severity=request.form.get("severity"),
    )
    db.session.add(v)
    db.session.commit()
    return redirect(url_for("inspection_view", id=id))


@app.route("/inspections/<int:id>/photo", methods=["POST"])
@login_required
def inspection_photo_upload(id):
    file, path = save_file(request.files.get("photo"), "inspection_photos")
    if file:
        photo = InspectionPhoto(
            inspection_id=id,
            filename=file,
            filepath=path,
            caption=request.form.get("caption"),
            latitude=request.form.get("latitude", type=float),
            longitude=request.form.get("longitude", type=float),
        )
        db.session.add(photo)
        db.session.commit()
    return redirect(url_for("inspection_view", id=id))


# ────────────────────────────────────────────────────────────
# MODULE 3: EMERGENCY INCIDENT MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/incidents")
@login_required
def incident_dashboard():
    stats = {
        "active": Incident.query.filter(Incident.status.in_(["reported", "dispatched", "active"])).count(),
        "total": Incident.query.count(),
    }
    incidents = Incident.query.order_by(Incident.created_at.desc()).all()
    return render_template("modules/incident/dashboard.html", stats=stats, incidents=incidents)


@app.route("/incidents/new", methods=["GET", "POST"])
@login_required
def incident_new():
    if request.method == "POST":
        inc = Incident(
            incident_no=f"INC-{uuid.uuid4().hex[:8].upper()}",
            incident_type=request.form["incident_type"],
            location=request.form["location"],
            region=request.form.get("region"),
            latitude=request.form.get("latitude", type=float),
            longitude=request.form.get("longitude", type=float),
            description=request.form.get("description"),
            reported_by=request.form.get("reported_by"),
            reported_phone=request.form.get("reported_phone"),
            severity=request.form.get("severity"),
            dispatched_by=current_user.id,
            dispatch_time=datetime.utcnow(),
        )
        db.session.add(inc)
        db.session.commit()
        log_action(current_user.id, "create", "incident", f"Incident {inc.incident_no} reported")
        flash("Incident reported successfully.", "success")
        return redirect(url_for("incident_dashboard"))
    return render_template("modules/incident/incident_form.html")


@app.route("/incidents/<int:id>")
@login_required
def incident_view(id):
    inc = Incident.query.get_or_404(id)
    return render_template("modules/incident/incident_view.html", inc=inc)


@app.route("/incidents/<int:id>/update", methods=["POST"])
@login_required
def incident_update(id):
    inc = Incident.query.get_or_404(id)
    inc.status = request.form.get("status", inc.status)
    if request.form.get("arrival_time"):
        inc.arrival_time = datetime.strptime(request.form["arrival_time"], "%Y-%m-%dT%H:%M")
    if request.form.get("closed_time"):
        inc.closed_time = datetime.strptime(request.form["closed_time"], "%Y-%m-%dT%H:%M")
    inc.casualties = request.form.get("casualties", type=int) or inc.casualties
    inc.fatalities = request.form.get("fatalities", type=int) or inc.fatalities
    inc.property_damage_estimate = request.form.get("property_damage_estimate", type=float)
    db.session.commit()
    log_action(current_user.id, "update", "incident", f"Incident {inc.incident_no} updated to {inc.status}")
    flash("Incident updated.", "success")
    return redirect(url_for("incident_view", id=id))


@app.route("/incidents/<int:id>/resource", methods=["POST"])
@login_required
def incident_resource_add(id):
    r = IncidentResource(
        incident_id=id,
        resource_type=request.form["resource_type"],
        identifier=request.form.get("identifier"),
    )
    db.session.add(r)
    db.session.commit()
    return redirect(url_for("incident_view", id=id))


# ────────────────────────────────────────────────────────────
# MODULE 4: FIRE INVESTIGATION MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/investigations")
@login_required
def investigation_dashboard():
    stats = {
        "open": Investigation.query.filter_by(status="open").count(),
        "closed": Investigation.query.filter_by(status="closed").count(),
        "total": Investigation.query.count(),
    }
    investigations = Investigation.query.order_by(Investigation.created_at.desc()).all()
    return render_template("modules/investigation/dashboard.html", stats=stats, investigations=investigations)


@app.route("/investigations/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "inspector", "supervisor")
def investigation_new():
    incidents = Incident.query.all()
    investigators = User.query.filter(User.role.in_(["admin", "inspector", "supervisor"])).all()
    if request.method == "POST":
        inv = Investigation(
            case_no=f"CASE-{uuid.uuid4().hex[:8].upper()}",
            incident_id=request.form.get("incident_id", type=int),
            title=request.form["title"],
            region=request.form.get("region"),
            lead_investigator_id=request.form.get("lead_investigator_id", type=int),
        )
        db.session.add(inv)
        db.session.commit()
        log_action(current_user.id, "create", "investigation", f"Case {inv.case_no} opened")
        flash("Investigation case opened.", "success")
        return redirect(url_for("investigation_dashboard"))
    return render_template("modules/investigation/investigation_form.html", incidents=incidents, investigators=investigators)


@app.route("/investigations/<int:id>")
@login_required
def investigation_view(id):
    inv = Investigation.query.get_or_404(id)
    return render_template("modules/investigation/investigation_view.html", inv=inv)


@app.route("/investigations/<int:id>/update", methods=["POST"])
@login_required
def investigation_update(id):
    inv = Investigation.query.get_or_404(id)
    inv.status = request.form.get("status", inv.status)
    inv.cause_determination = request.form.get("cause_determination")
    inv.cause_description = request.form.get("cause_description")
    inv.origin = request.form.get("origin")
    inv.is_court_case = "is_court_case" in request.form
    inv.court_details = request.form.get("court_details")
    if request.form.get("status") == "closed":
        inv.closed_at = datetime.utcnow()
    db.session.commit()
    log_action(current_user.id, "update", "investigation", f"Case {inv.case_no} updated")
    flash("Investigation updated.", "success")
    return redirect(url_for("investigation_view", id=id))


@app.route("/investigations/<int:id>/evidence", methods=["POST"])
@login_required
def investigation_evidence_add(id):
    file, path = save_file(request.files.get("file"), "evidence")
    e = Evidence(
        investigation_id=id,
        evidence_no=f"EV-{uuid.uuid4().hex[:8].upper()}",
        description=request.form["description"],
        evidence_type=request.form.get("evidence_type"),
        location_found=request.form.get("location_found"),
        collected_by=current_user.id,
        collected_at=datetime.utcnow(),
        storage_location=request.form.get("storage_location"),
        file_path=path,
    )
    db.session.add(e)
    db.session.commit()
    return redirect(url_for("investigation_view", id=id))


@app.route("/investigations/<int:id>/witness", methods=["POST"])
@login_required
def investigation_witness_add(id):
    w = WitnessStatement(
        investigation_id=id,
        witness_name=request.form["witness_name"],
        witness_contact=request.form.get("witness_contact"),
        statement=request.form["statement"],
        recorded_by=current_user.id,
    )
    db.session.add(w)
    db.session.commit()
    return redirect(url_for("investigation_view", id=id))


# ────────────────────────────────────────────────────────────
# MODULE 5: PUBLIC SERVICE PORTAL
# ────────────────────────────────────────────────────────────

@app.route("/public-portal/complaints")
@login_required
def complaints_list():
    complaints = PublicComplaint.query.order_by(PublicComplaint.created_at.desc()).all()
    return render_template("modules/public_portal/complaints.html", complaints=complaints)


@app.route("/public-portal/complaints/<int:id>/update", methods=["POST"])
@login_required
def complaint_update(id):
    c = PublicComplaint.query.get_or_404(id)
    c.status = request.form.get("status", c.status)
    c.assigned_to = request.form.get("assigned_to", type=int)
    c.resolution = request.form.get("resolution")
    if c.status == "resolved":
        c.resolved_at = datetime.utcnow()
    db.session.commit()
    flash("Complaint updated.", "success")
    return redirect(url_for("complaints_list"))


@app.route("/public-portal/hazards")
@login_required
def hazards_list():
    hazards = HazardReport.query.order_by(HazardReport.created_at.desc()).all()
    return render_template("modules/public_portal/hazards.html", hazards=hazards)


@app.route("/public-portal/hazards/<int:id>/update", methods=["POST"])
@login_required
def hazard_update(id):
    h = HazardReport.query.get_or_404(id)
    h.status = request.form.get("status", h.status)
    h.assigned_to = request.form.get("assigned_to", type=int)
    h.action_taken = request.form.get("action_taken")
    if h.status == "resolved":
        h.resolved_at = datetime.utcnow()
    db.session.commit()
    flash("Hazard report updated.", "success")
    return redirect(url_for("hazards_list"))


@app.route("/public-portal/training-registrations")
@login_required
def training_registrations_list():
    regs = TrainingRegistration.query.order_by(TrainingRegistration.created_at.desc()).all()
    return render_template("modules/public_portal/training_registrations.html", registrations=regs)


# ────────────────────────────────────────────────────────────
# MODULE 6: HUMAN RESOURCE MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/hr")
@login_required
def hr_dashboard():
    stats = {
        "total": User.query.filter_by(is_active=True).count(),
        "pending_leave": LeaveRequest.query.filter_by(status="pending").count(),
    }
    employees = User.query.order_by(User.last_name).all()
    leaves = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).limit(10).all()
    return render_template("modules/hr/dashboard.html", stats=stats, employees=employees, leaves=leaves)


@app.route("/hr/employees")
@login_required
def hr_employees():
    employees = User.query.order_by(User.last_name).all()
    stations = Station.query.all()
    return render_template("modules/hr/employees.html", employees=employees, stations=stations)


@app.route("/hr/employees/new", methods=["GET", "POST"])
@login_required
@role_required("admin")
def hr_employee_new():
    stations = Station.query.all()
    if request.method == "POST":
        user = User(
            username=request.form["username"],
            email=request.form["email"],
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            role=request.form["role"],
            phone=request.form.get("phone"),
            region=request.form.get("region"),
            position=request.form.get("position"),
            station_id=request.form.get("station_id", type=int),
        )
        user.set_password(request.form["password"])
        file, path = save_file(request.files.get("photo"), "employee_photos")
        if file:
            user.photo = path
        db.session.add(user)
        db.session.commit()
        log_action(current_user.id, "create", "hr", f"Employee {user.username} created")
        flash("Employee added successfully.", "success")
        return redirect(url_for("hr_employees"))
    return render_template("modules/hr/employee_form.html", stations=stations)


@app.route("/hr/employees/<int:id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def hr_employee_edit(id):
    user = User.query.get_or_404(id)
    user.first_name = request.form.get("first_name", user.first_name)
    user.last_name = request.form.get("last_name", user.last_name)
    user.email = request.form.get("email", user.email)
    user.phone = request.form.get("phone", user.phone)
    user.region = request.form.get("region", user.region)
    user.position = request.form.get("position", user.position)
    user.role = request.form.get("role", user.role)
    user.station_id = request.form.get("station_id", type=int)
    user.is_active = "is_active" in request.form
    file, path = save_file(request.files.get("photo"), "employee_photos")
    if file:
        user.photo = path
    db.session.commit()
    flash("Employee updated.", "success")
    return redirect(url_for("hr_employees"))


@app.route("/hr/leave")
@login_required
def hr_leave():
    leaves = LeaveRequest.query.order_by(LeaveRequest.created_at.desc()).all()
    return render_template("modules/hr/leave.html", leaves=leaves)


@app.route("/hr/leave/apply", methods=["POST"])
@login_required
def hr_leave_apply():
    lr = LeaveRequest(
        user_id=current_user.id,
        leave_type=request.form["leave_type"],
        start_date=datetime.strptime(request.form["start_date"], "%Y-%m-%d").date(),
        end_date=datetime.strptime(request.form["end_date"], "%Y-%m-%d").date(),
        reason=request.form.get("reason"),
    )
    db.session.add(lr)
    db.session.commit()
    flash("Leave request submitted.", "success")
    return redirect(url_for("hr_dashboard"))


@app.route("/hr/leave/<int:id>/approve", methods=["POST"])
@login_required
@role_required("admin", "supervisor")
def hr_leave_approve(id):
    lr = LeaveRequest.query.get_or_404(id)
    lr.status = request.form["status"]
    lr.approved_by = current_user.id
    db.session.commit()
    flash(f"Leave {lr.status}.", "success")
    return redirect(url_for("hr_leave"))


@app.route("/hr/attendance")
@login_required
def hr_attendance():
    today = date.today()
    records = Attendance.query.filter_by(date=today).all()
    all_users = User.query.filter_by(is_active=True).all()
    return render_template("modules/hr/attendance.html", records=records, users=all_users, today=today)


@app.route("/hr/attendance/checkin", methods=["POST"])
@login_required
def hr_attendance_checkin():
    existing = Attendance.query.filter_by(user_id=current_user.id, date=date.today()).first()
    if not existing:
        a = Attendance(user_id=current_user.id, check_in=datetime.utcnow(), status="present")
        db.session.add(a)
        db.session.commit()
        flash("Checked in.", "success")
    return redirect(url_for("hr_attendance"))


@app.route("/hr/attendance/checkout", methods=["POST"])
@login_required
def hr_attendance_checkout():
    rec = Attendance.query.filter_by(user_id=current_user.id, date=date.today()).first()
    if rec:
        rec.check_out = datetime.utcnow()
        db.session.commit()
        flash("Checked out.", "success")
    return redirect(url_for("hr_attendance"))


@app.route("/hr/attendance/<int:id>/set", methods=["POST"])
@login_required
@role_required("admin")
def hr_attendance_set(id):
    a = Attendance(
        user_id=id,
        date=datetime.strptime(request.form["date"], "%Y-%m-%d").date(),
        status=request.form["status"],
    )
    db.session.add(a)
    db.session.commit()
    return redirect(url_for("hr_attendance"))


# ────────────────────────────────────────────────────────────
# MODULE 7: TRAINING MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/training")
@login_required
def training_dashboard():
    stats = {
        "courses": Course.query.count(),
        "upcoming": Course.query.filter_by(status="upcoming").count(),
        "enrollments": CourseEnrollment.query.count(),
    }
    courses = Course.query.order_by(Course.start_date.desc()).all()
    return render_template("modules/training/dashboard.html", stats=stats, courses=courses)


@app.route("/training/courses/new", methods=["GET", "POST"])
@login_required
@role_required("admin", "supervisor")
def training_course_new():
    instructors = User.query.filter(User.role.in_(["admin", "supervisor", "trainer"])).all()
    if request.method == "POST":
        c = Course(
            code=request.form["code"],
            title=request.form["title"],
            description=request.form.get("description"),
            duration_hours=request.form.get("duration_hours", type=int),
            max_participants=request.form.get("max_participants", type=int),
            instructor_id=request.form.get("instructor_id", type=int),
            start_date=datetime.strptime(request.form["start_date"], "%Y-%m-%dT%H:%M") if request.form.get("start_date") else None,
            end_date=datetime.strptime(request.form["end_date"], "%Y-%m-%dT%H:%M") if request.form.get("end_date") else None,
        )
        file, path = save_file(request.files.get("photo"), "course_photos")
        if file:
            c.photo = path
        db.session.add(c)
        db.session.commit()
        flash("Course created.", "success")
        return redirect(url_for("training_dashboard"))
    return render_template("modules/training/course_form.html", instructors=instructors)


@app.route("/training/courses/<int:id>")
@login_required
def training_course_view(id):
    course = Course.query.get_or_404(id)
    return render_template("modules/training/course_view.html", course=course)


@app.route("/training/courses/<int:id>/enroll", methods=["POST"])
@login_required
def training_enroll(id):
    existing = CourseEnrollment.query.filter_by(course_id=id, user_id=current_user.id).first()
    if not existing:
        en = CourseEnrollment(course_id=id, user_id=current_user.id)
        db.session.add(en)
        db.session.commit()
        flash("Enrolled in course.", "success")
    return redirect(url_for("training_course_view", id=id))


@app.route("/training/exams/<int:id>/result", methods=["POST"])
@login_required
def training_exam_result(id):
    er = ExamResult(
        exam_id=id,
        user_id=current_user.id,
        score=request.form.get("score", type=int),
        passed=request.form.get("passed") == "on",
    )
    db.session.add(er)
    db.session.commit()
    flash("Exam result recorded.", "success")
    return redirect(url_for("training_dashboard"))


# ────────────────────────────────────────────────────────────
# MODULE 8: FLEET MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/fleet")
@login_required
def fleet_dashboard():
    stats = {
        "total": Vehicle.query.count(),
        "available": Vehicle.query.filter_by(status="available").count(),
        "maintenance": Vehicle.query.filter_by(status="maintenance").count(),
        "pending_maint": MaintenanceRecord.query.filter_by(status="scheduled").count(),
    }
    vehicles = Vehicle.query.order_by(Vehicle.created_at.desc()).all()
    return render_template("modules/fleet/dashboard.html", stats=stats, vehicles=vehicles)


@app.route("/fleet/vehicles/new", methods=["GET", "POST"])
@login_required
def fleet_vehicle_new():
    stations = Station.query.all()
    if request.method == "POST":
        v = Vehicle(
            registration_no=request.form["registration_no"],
            vehicle_type=request.form.get("vehicle_type"),
            make=request.form.get("make"),
            model=request.form.get("model"),
            year=request.form.get("year", type=int),
            station_id=request.form.get("station_id", type=int),
            fuel_type=request.form.get("fuel_type"),
            tank_capacity=request.form.get("tank_capacity", type=float),
            insurance_expiry=datetime.strptime(request.form["insurance_expiry"], "%Y-%m-%d").date() if request.form.get("insurance_expiry") else None,
        )
        file, path = save_file(request.files.get("photo"), "vehicle_photos")
        if file:
            v.photo = path
        db.session.add(v)
        db.session.commit()
        flash("Vehicle added.", "success")
        return redirect(url_for("fleet_dashboard"))
    return render_template("modules/fleet/vehicle_form.html", stations=stations)


@app.route("/fleet/vehicles/<int:id>")
@login_required
def fleet_vehicle_view(id):
    v = Vehicle.query.get_or_404(id)
    return render_template("modules/fleet/vehicle_view.html", v=v)


@app.route("/fleet/maintenance/new", methods=["POST"])
@login_required
def fleet_maintenance_new():
    m = MaintenanceRecord(
        vehicle_id=request.form["vehicle_id"],
        maintenance_type=request.form.get("maintenance_type"),
        description=request.form.get("description"),
        cost=request.form.get("cost", type=float),
        service_provider=request.form.get("service_provider"),
        scheduled_date=datetime.strptime(request.form["scheduled_date"], "%Y-%m-%d").date() if request.form.get("scheduled_date") else None,
    )
    db.session.add(m)
    vehicle = Vehicle.query.get(m.vehicle_id)
    vehicle.status = "maintenance"
    db.session.commit()
    flash("Maintenance record added.", "success")
    return redirect(url_for("fleet_vehicle_view", id=m.vehicle_id))


@app.route("/fleet/fuel/new", methods=["POST"])
@login_required
def fleet_fuel_new():
    f = FuelLog(
        vehicle_id=request.form["vehicle_id"],
        driver_id=current_user.id,
        liters=request.form.get("liters", type=float),
        cost=request.form.get("cost", type=float),
        station_name=request.form.get("station_name"),
        mileage=request.form.get("mileage", type=float),
    )
    db.session.add(f)
    vehicle = Vehicle.query.get(f.vehicle_id)
    if f.mileage:
        vehicle.mileage = f.mileage
    db.session.commit()
    flash("Fuel log added.", "success")
    return redirect(url_for("fleet_vehicle_view", id=f.vehicle_id))


# ────────────────────────────────────────────────────────────
# MODULE 9: ASSET MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/assets")
@login_required
def asset_dashboard():
    stats = {
        "total": Asset.query.count(),
        "active": Asset.query.filter_by(status="active").count(),
        "disposed": Asset.query.filter_by(status="disposed").count(),
    }
    assets = Asset.query.order_by(Asset.created_at.desc()).all()
    stations = Station.query.all()
    return render_template("modules/asset/dashboard.html", stats=stats, assets=assets, stations=stations)


@app.route("/assets/new", methods=["POST"])
@login_required
def asset_new():
    a = Asset(
        asset_tag=request.form["asset_tag"],
        name=request.form["name"],
        description=request.form.get("description"),
        category=request.form.get("category"),
        station_id=request.form.get("station_id", type=int),
        assigned_to=request.form.get("assigned_to", type=int),
        purchase_date=datetime.strptime(request.form["purchase_date"], "%Y-%m-%d").date() if request.form.get("purchase_date") else None,
        purchase_cost=request.form.get("purchase_cost", type=float),
        current_value=request.form.get("current_value", type=float),
        barcode=request.form.get("barcode"),
        location=request.form.get("location"),
    )
    db.session.add(a)
    db.session.commit()
    flash("Asset added.", "success")
    return redirect(url_for("asset_dashboard"))


@app.route("/assets/<int:id>/update", methods=["POST"])
@login_required
def asset_update(id):
    a = Asset.query.get_or_404(id)
    a.status = request.form.get("status", a.status)
    a.current_value = request.form.get("current_value", type=float) or a.current_value
    a.location = request.form.get("location", a.location)
    a.notes = request.form.get("notes")
    db.session.commit()
    flash("Asset updated.", "success")
    return redirect(url_for("asset_dashboard"))


# ────────────────────────────────────────────────────────────
# MODULE 10: FINANCIAL MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/finance")
@login_required
@role_required("admin", "finance", "supervisor")
def finance_dashboard():
    fees = FeeCollection.query.order_by(FeeCollection.collected_at.desc()).all()
    total_revenue = db.session.query(db.func.sum(FeeCollection.amount)).filter_by(status="paid").scalar() or 0
    budgets = Budget.query.all()
    transactions = FinancialTransaction.query.order_by(FinancialTransaction.created_at.desc()).limit(20).all()
    return render_template("modules/finance/dashboard.html", fees=fees, total_revenue=total_revenue, budgets=budgets, transactions=transactions)


@app.route("/finance/fees/new", methods=["POST"])
@login_required
def finance_fee_new():
    f = FeeCollection(
        receipt_no=f"RCP-{uuid.uuid4().hex[:8].upper()}",
        payer_name=request.form["payer_name"],
        payer_email=request.form.get("payer_email"),
        fee_type=request.form["fee_type"],
        amount=request.form.get("amount", type=float),
        payment_method=request.form.get("payment_method"),
        collected_by=current_user.id,
        status="paid",
    )
    db.session.add(f)
    db.session.commit()
    flash("Payment recorded.", "success")
    return redirect(url_for("finance_dashboard"))


@app.route("/finance/budgets/new", methods=["POST"])
@login_required
@role_required("admin")
def finance_budget_new():
    b = Budget(
        fiscal_year=request.form.get("fiscal_year", type=int),
        category=request.form["category"],
        allocated_amount=request.form.get("allocated_amount", type=float),
        remaining=request.form.get("allocated_amount", type=float),
    )
    db.session.add(b)
    db.session.commit()
    flash("Budget entry added.", "success")
    return redirect(url_for("finance_dashboard"))


@app.route("/finance/transactions/new", methods=["POST"])
@login_required
def finance_transaction_new():
    t = FinancialTransaction(
        transaction_type=request.form["transaction_type"],
        description=request.form.get("description"),
        amount=request.form.get("amount", type=float),
        category=request.form.get("category"),
        reference=request.form.get("reference"),
        initiated_by=current_user.id,
    )
    db.session.add(t)
    db.session.commit()
    flash("Transaction recorded.", "success")
    return redirect(url_for("finance_dashboard"))


# ────────────────────────────────────────────────────────────
# MODULE 11: DOCUMENT MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/documents")
@login_required
def document_dashboard():
    stats = {
        "total": Document.query.count(),
        "archived": Document.query.filter_by(is_archived=True).count(),
    }
    documents = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("modules/document/dashboard.html", stats=stats, documents=documents)


@app.route("/documents/upload", methods=["GET", "POST"])
@login_required
def document_upload():
    if request.method == "POST":
        file, path = save_file(request.files.get("file"), "documents")
        if file:
            doc = Document(
                title=request.form["title"],
                description=request.form.get("description"),
                category=request.form.get("category"),
                file_name=file,
                file_path=path,
                file_size=os.path.getsize(path) if path else 0,
                file_type=file.rsplit(".", 1)[1].lower() if "." in file else None,
                uploaded_by=current_user.id,
                access_level=request.form.get("access_level", "internal"),
            )
            db.session.add(doc)
            db.session.commit()
            log_action(current_user.id, "upload", "document", f"Document {doc.title} uploaded")
            flash("Document uploaded.", "success")
            return redirect(url_for("document_dashboard"))
        flash("Upload failed.", "danger")
    return render_template("modules/document/upload.html")


@app.route("/documents/<int:id>/archive", methods=["POST"])
@login_required
def document_archive(id):
    doc = Document.query.get_or_404(id)
    doc.is_archived = not doc.is_archived
    db.session.commit()
    flash(f"Document {'archived' if doc.is_archived else 'unarchived'}.", "success")
    return redirect(url_for("document_dashboard"))


@app.route("/documents/<int:id>/download")
@login_required
def document_download(id):
    doc = Document.query.get_or_404(id)
    if doc.file_path and os.path.exists(doc.file_path):
        return send_from_directory(os.path.dirname(doc.file_path), os.path.basename(doc.file_path))
    flash("File not found.", "danger")
    return redirect(url_for("document_dashboard"))


# ────────────────────────────────────────────────────────────
# MODULE 12: STATION OPERATIONS
# ────────────────────────────────────────────────────────────

@app.route("/station-operations")
@login_required
def station_ops_dashboard():
    stations = Station.query.all()
    rosters = DutyRoster.query.filter_by(shift_date=date.today()).all()
    logs = OccurrenceLog.query.order_by(OccurrenceLog.created_at.desc()).limit(20).all()
    return render_template("modules/station/dashboard.html", stations=stations, rosters=rosters, logs=logs)


@app.route("/station-operations/rosters", methods=["GET", "POST"])
@login_required
def station_rosters():
    if request.method == "POST":
        r = DutyRoster(
            station_id=request.form["station_id"],
            user_id=request.form["user_id"],
            shift_date=datetime.strptime(request.form["shift_date"], "%Y-%m-%d").date(),
            shift_type=request.form["shift_type"],
            start_time=datetime.strptime(request.form["start_time"], "%H:%M").time() if request.form.get("start_time") else None,
            end_time=datetime.strptime(request.form["end_time"], "%H:%M").time() if request.form.get("end_time") else None,
            role=request.form.get("role"),
        )
        db.session.add(r)
        db.session.commit()
        flash("Roster entry added.", "success")
        return redirect(url_for("station_ops_dashboard"))
    stations = Station.query.all()
    personnel = User.query.filter_by(is_active=True).all()
    rosters = DutyRoster.query.order_by(DutyRoster.shift_date.desc()).all()
    return render_template("modules/station/rosters.html", stations=stations, personnel=personnel, rosters=rosters)


@app.route("/station-operations/logs/new", methods=["POST"])
@login_required
def station_log_new():
    last = OccurrenceLog.query.filter_by(station_id=request.form["station_id"], log_date=date.today()).order_by(OccurrenceLog.entry_no.desc()).first()
    entry_no = (last.entry_no + 1) if last else 1
    log = OccurrenceLog(
        station_id=request.form["station_id"],
        log_date=date.today(),
        entry_no=entry_no,
        time=datetime.strptime(request.form["time"], "%H:%M").time(),
        description=request.form["description"],
        incident_type=request.form.get("incident_type"),
        recorded_by=current_user.id,
    )
    db.session.add(log)
    db.session.commit()
    flash("Occurrence logged.", "success")
    return redirect(url_for("station_ops_dashboard"))


@app.route("/stations/new", methods=["POST"])
@login_required
@role_required("admin")
def station_new():
    s = Station(
        name=request.form["name"],
        code=request.form["code"],
        address=request.form.get("address"),
        city=request.form.get("city"),
        country=request.form.get("country", "Guyana"),
        region=request.form.get("region"),
        phone=request.form.get("phone"),
    )
    db.session.add(s)
    db.session.commit()
    flash("Station added.", "success")
    return redirect(url_for("station_ops_dashboard"))


# ────────────────────────────────────────────────────────────
# MODULE 13: DISASTER MANAGEMENT
# ────────────────────────────────────────────────────────────

@app.route("/disaster")
@login_required
def disaster_dashboard():
    stats = {
        "active": DisasterEvent.query.filter_by(status="active").count(),
        "total": DisasterEvent.query.count(),
        "shelters": Shelter.query.count(),
    }
    events = DisasterEvent.query.order_by(DisasterEvent.declared_at.desc()).all()
    shelters = Shelter.query.all()
    return render_template("modules/disaster/dashboard.html", stats=stats, events=events, shelters=shelters)


@app.route("/disaster/events/new", methods=["POST"])
@login_required
@role_required("admin", "supervisor")
def disaster_event_new():
    e = DisasterEvent(
        event_no=f"DR-{uuid.uuid4().hex[:8].upper()}",
        event_type=request.form["event_type"],
        location=request.form["location"],
        region=request.form.get("region"),
        latitude=request.form.get("latitude", type=float),
        longitude=request.form.get("longitude", type=float),
        description=request.form.get("description"),
        severity=request.form.get("severity"),
        declared_by=current_user.id,
    )
    db.session.add(e)
    db.session.commit()
    flash("Disaster event declared.", "success")
    return redirect(url_for("disaster_dashboard"))


@app.route("/disaster/events/<int:id>/update", methods=["POST"])
@login_required
def disaster_event_update(id):
    e = DisasterEvent.query.get_or_404(id)
    e.status = request.form.get("status", e.status)
    if e.status == "resolved":
        e.resolved_at = datetime.utcnow()
    db.session.commit()
    flash("Event updated.", "success")
    return redirect(url_for("disaster_dashboard"))


@app.route("/disaster/deploy", methods=["POST"])
@login_required
def disaster_deploy():
    d = DisasterDeployment(
        event_id=request.form["event_id"],
        resource_type=request.form.get("resource_type"),
        identifier=request.form.get("identifier"),
        quantity=request.form.get("quantity", type=int),
        deployed_to=request.form.get("deployed_to"),
    )
    db.session.add(d)
    db.session.commit()
    flash("Resource deployed.", "success")
    return redirect(url_for("disaster_dashboard"))


@app.route("/disaster/shelters/new", methods=["POST"])
@login_required
def disaster_shelter_new():
    s = Shelter(
        name=request.form["name"],
        region=request.form.get("region"),
        address=request.form.get("address"),
        capacity=request.form.get("capacity", type=int),
        contact=request.form.get("contact"),
        latitude=request.form.get("latitude", type=float),
        longitude=request.form.get("longitude", type=float),
    )
    db.session.add(s)
    db.session.commit()
    flash("Shelter added.", "success")
    return redirect(url_for("disaster_dashboard"))


# ────────────────────────────────────────────────────────────
# MODULE 14: GIS & MAPPING
# ────────────────────────────────────────────────────────────

@app.route("/gis")
@login_required
def gis_dashboard():
    hydrants = Hydrant.query.all()
    stations = Station.query.all()
    incidents = Incident.query.filter(Incident.latitude.isnot(None), Incident.longitude.isnot(None)).all()
    risk_zones = RiskZone.query.all()
    hydrant_data = [
        {"id": h.id, "hydrant_no": h.hydrant_no, "location": h.location,
         "latitude": h.latitude, "longitude": h.longitude, "flow_rate": h.flow_rate}
        for h in hydrants
    ]
    return render_template("modules/gis/dashboard.html", hydrants=hydrants, stations=stations,
                           incidents=incidents, risk_zones=risk_zones, hydrant_data=hydrant_data)


@app.route("/gis/hydrants/new", methods=["POST"])
@login_required
def hydrant_new():
    h = Hydrant(
        hydrant_no=request.form["hydrant_no"],
        location=request.form.get("location"),
        region=request.form.get("region"),
        latitude=request.form.get("latitude", type=float),
        longitude=request.form.get("longitude", type=float),
        flow_rate=request.form.get("flow_rate", type=float),
    )
    db.session.add(h)
    db.session.commit()
    flash("Hydrant added.", "success")
    return redirect(url_for("gis_dashboard"))


@app.route("/gis/hydrants/<int:id>/edit", methods=["POST"])
@login_required
def hydrant_edit(id):
    h = Hydrant.query.get_or_404(id)
    h.hydrant_no = request.form.get("hydrant_no", h.hydrant_no)
    h.location = request.form.get("location", h.location)
    h.region = request.form.get("region", h.region)
    h.latitude = request.form.get("latitude", type=float) or h.latitude
    h.longitude = request.form.get("longitude", type=float) or h.longitude
    h.flow_rate = request.form.get("flow_rate", type=float)
    h.status = request.form.get("status", h.status)
    db.session.commit()
    flash("Hydrant updated.", "success")
    return redirect(url_for("gis_dashboard"))


@app.route("/gis/risk-zones/new", methods=["POST"])
@login_required
def risk_zone_new():
    rz = RiskZone(
        zone_name=request.form["zone_name"],
        region=request.form.get("region"),
        risk_level=request.form.get("risk_level"),
        population_density=request.form.get("population_density", type=int),
        notes=request.form.get("notes"),
    )
    db.session.add(rz)
    db.session.commit()
    flash("Risk zone added.", "success")
    return redirect(url_for("gis_dashboard"))


# ────────────────────────────────────────────────────────────
# MODULE 15: EXECUTIVE DASHBOARD
# ────────────────────────────────────────────────────────────

@app.route("/executive-dashboard")
@login_required
@role_required("admin", "supervisor", "executive")
def executive_dashboard():
    stats = get_dashboard_stats()
    incidents_by_type = db.session.query(
        Incident.incident_type, db.func.count(Incident.id)
    ).group_by(Incident.incident_type).all()
    certs_by_month = db.session.query(
        db.func.strftime("%Y-%m", FireCertificate.created_at),
        db.func.count(FireCertificate.id),
    ).group_by(db.func.strftime("%Y-%m", FireCertificate.created_at)).all()
    revenue_by_month = db.session.query(
        db.func.strftime("%Y-%m", FeeCollection.collected_at),
        db.func.sum(FeeCollection.amount),
    ).filter(FeeCollection.status == "paid").group_by(
        db.func.strftime("%Y-%m", FeeCollection.collected_at)
    ).all()
    return render_template(
        "modules/executive/dashboard.html",
        stats=stats,
        incidents_by_type=incidents_by_type,
        certs_by_month=certs_by_month,
        revenue_by_month=revenue_by_month,
    )


# ────────────────────────────────────────────────────────────
# AUDIT LOG VIEWER
# ────────────────────────────────────────────────────────────

@app.route("/audit-logs")
@login_required
@role_required("admin")
def audit_logs():
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(100).all()
    return render_template("audit_logs.html", logs=logs)


# ────────────────────────────────────────────────────────────
# SYSTEM ADMINISTRATION
# ────────────────────────────────────────────────────────────

@app.route("/admin/system")
@login_required
@role_required("admin")
def system_admin_dashboard():
    stats = {
        "total_users": User.query.count(),
        "active_users": User.query.filter_by(is_active=True).count(),
        "stations": Station.query.count(),
        "roles": db.session.query(User.role, db.func.count(User.id)).group_by(User.role).all(),
    }
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    return render_template("modules/admin/dashboard.html", stats=stats, recent_users=recent_users)


@app.route("/admin/users")
@login_required
@role_required("admin")
def system_admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    stations = Station.query.all()
    return render_template("modules/admin/users.html", users=users, stations=stations)


@app.route("/admin/users/create", methods=["GET", "POST"])
@login_required
@role_required("admin")
def system_admin_user_create():
    stations = Station.query.all()
    if request.method == "POST":
        existing = User.query.filter(
            (User.username == request.form["username"]) | (User.email == request.form["email"])
        ).first()
        if existing:
            flash("Username or email already exists.", "danger")
            return render_template("modules/admin/user_form.html", stations=stations)
        user = User(
            username=request.form["username"],
            email=request.form["email"],
            first_name=request.form["first_name"],
            last_name=request.form["last_name"],
            role=request.form["role"],
            phone=request.form.get("phone"),
            region=request.form.get("region"),
            position=request.form.get("position"),
            station_id=request.form.get("station_id", type=int) or None,
            is_active=True,
        )
        user.set_password(request.form["password"])
        file, path = save_file(request.files.get("photo"), "employee_photos")
        if file:
            user.photo = path
        db.session.add(user)
        db.session.commit()
        log_action(current_user.id, "create", "system_admin", f"User {user.username} ({user.role}) created")
        flash(f"User {user.username} created successfully.", "success")
        return redirect(url_for("system_admin_users"))
    return render_template("modules/admin/user_form.html", stations=stations)


@app.route("/admin/users/<int:id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def system_admin_user_edit(id):
    user = User.query.get_or_404(id)
    user.first_name = request.form.get("first_name", user.first_name)
    user.last_name = request.form.get("last_name", user.last_name)
    user.email = request.form.get("email", user.email)
    user.phone = request.form.get("phone", user.phone)
    user.region = request.form.get("region", user.region)
    user.role = request.form.get("role", user.role)
    user.position = request.form.get("position", user.position)
    user.station_id = request.form.get("station_id", type=int) or None
    user.is_active = "is_active" in request.form
    if request.form.get("password"):
        user.set_password(request.form["password"])
    file, path = save_file(request.files.get("photo"), "employee_photos")
    if file:
        user.photo = path
    db.session.commit()
    log_action(current_user.id, "edit", "system_admin", f"User {user.username} updated")
    flash(f"User {user.username} updated.", "success")
    return redirect(url_for("system_admin_users"))


@app.route("/admin/stations", methods=["GET", "POST"])
@login_required
@role_required("admin")
def system_admin_stations():
    if request.method == "POST":
        s = Station(
            name=request.form["name"],
            code=request.form["code"],
            address=request.form.get("address"),
            city=request.form.get("city"),
            country=request.form.get("country", "Guyana"),
            region=request.form.get("region"),
            phone=request.form.get("phone"),
        )
        db.session.add(s)
        db.session.commit()
        log_action(current_user.id, "create", "system_admin", f"Station {s.name} created")
        flash(f"Station {s.name} added.", "success")
        return redirect(url_for("system_admin_stations"))
    stations = Station.query.all()
    return render_template("modules/admin/stations.html", stations=stations)


@app.route("/admin/stations/<int:id>/edit", methods=["POST"])
@login_required
@role_required("admin")
def system_admin_station_edit(id):
    s = Station.query.get_or_404(id)
    s.name = request.form.get("name", s.name)
    s.code = request.form.get("code", s.code)
    s.address = request.form.get("address", s.address)
    s.city = request.form.get("city", s.city)
    s.country = request.form.get("country", s.country)
    s.region = request.form.get("region", s.region)
    s.phone = request.form.get("phone", s.phone)
    s.is_active = "is_active" in request.form
    db.session.commit()
    flash(f"Station {s.name} updated.", "success")
    return redirect(url_for("system_admin_stations"))


# ────────────────────────────────────────────────────────────
# PUBLIC PORTAL - EXTERNAL FACING
# ────────────────────────────────────────────────────────────

@app.route("/public")
def public_portal():
    return render_template("modules/public_portal/public_home.html")


@app.route("/public/certificate/apply", methods=["GET", "POST"])
def public_certificate_apply():
    if request.method == "POST":
        cert = FireCertificate(
            certificate_no=f"FC-{uuid.uuid4().hex[:8].upper()}",
            applicant_name=request.form["applicant_name"],
            applicant_email=request.form.get("applicant_email"),
            applicant_phone=request.form.get("applicant_phone"),
            business_name=request.form.get("business_name"),
            business_address=request.form.get("business_address"),
            property_type=request.form.get("property_type"),
            status="pending",
        )
        db.session.add(cert)
        db.session.commit()
        flash("Application submitted. Reference: " + cert.certificate_no, "success")
        return redirect(url_for("public_portal"))
    return render_template("modules/public_portal/public_certificate.html")


@app.route("/public/complaint", methods=["GET", "POST"])
def public_complaint():
    if request.method == "POST":
        c = PublicComplaint(
            name=request.form.get("name"),
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            subject=request.form["subject"],
            description=request.form["description"],
            complaint_type=request.form.get("complaint_type"),
            region=request.form.get("region"),
        )
        db.session.add(c)
        db.session.commit()
        flash("Complaint submitted.", "success")
        return redirect(url_for("public_portal"))
    return render_template("modules/public_portal/public_complaint.html")


@app.route("/public/hazard", methods=["GET", "POST"])
def public_hazard():
    if request.method == "POST":
        h = HazardReport(
            reporter_name=request.form.get("reporter_name"),
            reporter_email=request.form.get("reporter_email"),
            reporter_phone=request.form.get("reporter_phone"),
            location=request.form["location"],
            description=request.form["description"],
            hazard_type=request.form.get("hazard_type"),
        )
        db.session.add(h)
        db.session.commit()
        flash("Hazard reported.", "success")
        return redirect(url_for("public_portal"))
    return render_template("modules/public_portal/public_hazard.html")


@app.route("/public/training/register", methods=["GET", "POST"])
def public_training_register():
    courses = Course.query.filter_by(status="upcoming").all()
    if request.method == "POST":
        r = TrainingRegistration(
            course_id=request.form.get("course_id", type=int),
            full_name=request.form["full_name"],
            email=request.form.get("email"),
            phone=request.form.get("phone"),
            organization=request.form.get("organization"),
        )
        db.session.add(r)
        db.session.commit()
        flash("Registration submitted.", "success")
        return redirect(url_for("public_portal"))
    return render_template("modules/public_portal/public_training.html", courses=courses)


@app.route("/public/status")
def public_status():
    ref = request.args.get("reference")
    cert = FireCertificate.query.filter_by(certificate_no=ref).first() if ref else None
    complaint = PublicComplaint.query.filter_by(id=ref).first() if ref else None
    return render_template("modules/public_portal/public_status.html", cert=cert, complaint=complaint)


# ────────────────────────────────────────────────────────────
# ERROR HANDLERS
# ────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("errors/404.html"), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template("errors/403.html"), 403


@app.errorhandler(500)
def server_error(e):
    return render_template("errors/500.html"), 500


# ────────────────────────────────────────────────────────────
# INIT & SEED
# ────────────────────────────────────────────────────────────

def seed_database():
    if User.query.first():
        return

    stations = [
        Station(name="Georgetown Central Fire Station", code="GT-CENTRAL", address="Main Street, Georgetown", city="Georgetown", country="Guyana", region="Region 4 - Demerara-Mahaica", phone="225-1111", latitude=6.8013, longitude=-58.1553),
        Station(name="Linden Fire Station", code="LIN", address="Mackenzie, Linden", city="Linden", country="Guyana", region="Region 10 - Upper Demerara-Berbice", phone="444-2222", latitude=6.0022, longitude=-58.3072),
        Station(name="New Amsterdam Fire Station", code="NAM", address="New Amsterdam", city="New Amsterdam", country="Guyana", region="Region 6 - East Berbice-Corentyne", phone="333-3333", latitude=6.2500, longitude=-57.5167),
    ]
    db.session.add_all(stations)
    db.session.commit()

    users = [
        ("admin", "admin@gfsmis.gov.gy", "Admin", "User", "admin", "Administrator", 1),
        ("inspector1", "inspector1@gfsmis.gov.gy", "John", "Doe", "inspector", "Fire Inspector", 1),
        ("officer1", "officer1@gfsmis.gov.gy", "Jane", "Smith", "officer", "Fire Officer", 1),
        ("finance1", "finance1@gfsmis.gov.gy", "Mark", "Brown", "finance", "Finance Officer", 1),
        ("trainer1", "trainer1@gfsmis.gov.gy", "Sarah", "Jones", "trainer", "Training Officer", 1),
        ("supervisor1", "supervisor1@gfsmis.gov.gy", "Mike", "Wilson", "supervisor", "Station Supervisor", 1),
        ("staff1", "staff1@gfsmis.gov.gy", "Lisa", "Taylor", "staff", "Firefighter", 2),
        ("exec1", "exec1@gfsmis.gov.gy", "Robert", "Davis", "executive", "Chief Fire Officer", 1),
    ]
    for username, email, fn, ln, role, pos, sid in users:
        u = User(
            username=username, email=email, first_name=fn, last_name=ln,
            role=role, position=pos, station_id=sid, is_active=True,
        )
        u.set_password("password123")
        db.session.add(u)
    db.session.commit()

    for i in range(5):
        cert = FireCertificate(
            certificate_no=f"FC-SEED-{i+1:04d}",
            applicant_name=f"Applicant {i+1}",
            applicant_email=f"app{i+1}@email.com",
            business_name=f"Business {i+1}",
            property_type="Commercial",
            status="approved" if i < 3 else "pending",
            issue_date=date.today() if i < 3 else None,
            submitted_by=2,
        )
        db.session.add(cert)
    db.session.commit()

    hydrant_data = [
        ("H-001", "Main Street & Church Street", 6.8050, -58.1550),
        ("H-002", "Regent Street & Camp Street", 6.8100, -58.1580),
        ("H-003", "Water Street & Broad Street", 6.8000, -58.1500),
    ]
    for hno, loc, lat, lon in hydrant_data:
        h = Hydrant(hydrant_no=hno, location=loc, latitude=lat, longitude=lon)
        db.session.add(h)
    db.session.commit()

    inc = Incident(
        incident_no="INC-SEED-001",
        incident_type="Structure Fire",
        location="Main Street, Georgetown",
        latitude=6.8050, longitude=-58.1550,
        description="Fire at commercial building",
        severity="high",
        status="active",
        dispatched_by=2,
        dispatch_time=datetime.utcnow(),
    )
    db.session.add(inc)
    db.session.commit()

    b1 = Budget(
        fiscal_year=2026,
        category="Operations",
        allocated_amount=50000000.0,
        spent_amount=12500000.0,
        remaining=37500000.0,
    )
    b2 = Budget(
        fiscal_year=2026,
        category="Training",
        allocated_amount=10000000.0,
        spent_amount=3000000.0,
        remaining=7000000.0,
    )
    b3 = Budget(
        fiscal_year=2026,
        category="Vehicle Maintenance",
        allocated_amount=15000000.0,
        spent_amount=5000000.0,
        remaining=10000000.0,
    )
    db.session.add_all([b1, b2, b3])
    db.session.commit()


with app.app_context():
    seed_database()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(debug=debug, host="0.0.0.0", port=port)
