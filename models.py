from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

REGIONS = [
    ("", "Select Region..."),
    ("Region 1 - Barima-Waini", "Region 1 - Barima-Waini"),
    ("Region 2 - Pomeroon-Supenaam", "Region 2 - Pomeroon-Supenaam"),
    ("Region 3 - Essequibo Islands-West Demerara", "Region 3 - Essequibo Islands-West Demerara"),
    ("Region 4 - Demerara-Mahaica", "Region 4 - Demerara-Mahaica"),
    ("Region 5 - Mahaica-Berbice", "Region 5 - Mahaica-Berbice"),
    ("Region 6 - East Berbice-Corentyne", "Region 6 - East Berbice-Corentyne"),
    ("Region 7 - Cuyuni-Mazaruni", "Region 7 - Cuyuni-Mazaruni"),
    ("Region 8 - Potaro-Siparuni", "Region 8 - Potaro-Siparuni"),
    ("Region 9 - Upper Takutu-Upper Essequibo", "Region 9 - Upper Takutu-Upper Essequibo"),
    ("Region 10 - Upper Demerara-Berbice", "Region 10 - Upper Demerara-Berbice"),
]


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    role = db.Column(
        db.String(20),
        nullable=False,
        default="staff",
    )
    phone = db.Column(db.String(20))
    photo = db.Column(db.String(500))
    region = db.Column(db.String(100))
    position = db.Column(db.String(100))
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id"))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Station(db.Model):
    __tablename__ = "stations"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    country = db.Column(db.String(100), default="Guyana")
    region = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    personnel = db.relationship("User", backref="station", lazy=True)


# ─── Module 1: Fire Prevention & Compliance ──────────────────────


class FireCertificate(db.Model):
    __tablename__ = "fire_certificates"
    id = db.Column(db.Integer, primary_key=True)
    certificate_no = db.Column(db.String(50), unique=True, nullable=False)
    applicant_name = db.Column(db.String(200), nullable=False)
    applicant_email = db.Column(db.String(120))
    applicant_phone = db.Column(db.String(20))
    business_name = db.Column(db.String(200))
    business_address = db.Column(db.Text)
    property_type = db.Column(db.String(100))
    status = db.Column(
        db.String(20), default="pending"
    )
    submitted_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    inspected_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    issue_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = db.relationship("CertificateDocument", backref="certificate", lazy=True)


class CertificateDocument(db.Model):
    __tablename__ = "certificate_documents"
    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey("fire_certificates.id"), nullable=False)
    filename = db.Column(db.String(255))
    filepath = db.Column(db.String(500))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class BuildingPlan(db.Model):
    __tablename__ = "building_plans"
    id = db.Column(db.Integer, primary_key=True)
    project_name = db.Column(db.String(200), nullable=False)
    applicant_name = db.Column(db.String(200), nullable=False)
    applicant_email = db.Column(db.String(120))
    address = db.Column(db.Text)
    plan_file = db.Column(db.String(500))
    status = db.Column(db.String(20), default="submitted")
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    review_notes = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)


class FireInspection(db.Model):
    __tablename__ = "fire_inspections"
    id = db.Column(db.Integer, primary_key=True)
    inspection_no = db.Column(db.String(50), unique=True, nullable=False)
    property_name = db.Column(db.String(200), nullable=False)
    property_address = db.Column(db.Text)
    property_type = db.Column(db.String(100))
    region = db.Column(db.String(100))
    photo = db.Column(db.String(500))
    inspection_type = db.Column(db.String(50))
    inspector_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    scheduled_date = db.Column(db.DateTime)
    conducted_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="scheduled")
    findings = db.Column(db.Text)
    recommendations = db.Column(db.Text)
    compliance_status = db.Column(db.String(20))
    follow_up_required = db.Column(db.Boolean, default=False)
    follow_up_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inspector = db.relationship("User", backref="inspections", lazy=True)
    photos = db.relationship("InspectionPhoto", backref="inspection", lazy=True)
    violations = db.relationship("Violation", backref="inspection", lazy=True)
    checklist_items = db.relationship("InspectionChecklistItem", backref="inspection", lazy=True)


class InspectionPhoto(db.Model):
    __tablename__ = "inspection_photos"
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("fire_inspections.id"), nullable=False)
    filename = db.Column(db.String(255))
    filepath = db.Column(db.String(500))
    caption = db.Column(db.String(200))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class InspectionChecklistItem(db.Model):
    __tablename__ = "inspection_checklist_items"
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("fire_inspections.id"), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    is_compliant = db.Column(db.Boolean)
    remarks = db.Column(db.Text)


class Violation(db.Model):
    __tablename__ = "violations"
    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("fire_inspections.id"), nullable=False)
    violation_code = db.Column(db.String(50))
    description = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20))
    status = db.Column(db.String(20), default="open")
    corrected_date = db.Column(db.Date)


# ─── Module 3: Emergency Incident Management ──────────────────


class Incident(db.Model):
    __tablename__ = "incidents"
    id = db.Column(db.Integer, primary_key=True)
    incident_no = db.Column(db.String(50), unique=True, nullable=False)
    incident_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(300), nullable=False)
    region = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    description = db.Column(db.Text)
    reported_by = db.Column(db.String(100))
    reported_phone = db.Column(db.String(20))
    severity = db.Column(db.String(20))
    status = db.Column(db.String(20), default="reported")
    dispatched_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    dispatch_time = db.Column(db.DateTime)
    arrival_time = db.Column(db.DateTime)
    closed_time = db.Column(db.DateTime)
    casualties = db.Column(db.Integer, default=0)
    fatalities = db.Column(db.Integer, default=0)
    property_damage_estimate = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    dispatched_by_user = db.relationship("User", backref="dispatched_incidents", lazy=True)
    resources = db.relationship("IncidentResource", backref="incident", lazy=True)
    responders = db.relationship("IncidentResponder", backref="incident", lazy=True)


class IncidentResource(db.Model):
    __tablename__ = "incident_resources"
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"), nullable=False)
    resource_type = db.Column(db.String(50))
    identifier = db.Column(db.String(100))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    released_at = db.Column(db.DateTime)


class IncidentResponder(db.Model):
    __tablename__ = "incident_responders"
    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    role = db.Column(db.String(50))
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="incident_assignments", lazy=True)


# ─── Module 4: Fire Investigation Management ──────────────────


class Investigation(db.Model):
    __tablename__ = "investigations"
    id = db.Column(db.Integer, primary_key=True)
    case_no = db.Column(db.String(50), unique=True, nullable=False)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id"))
    title = db.Column(db.String(200), nullable=False)
    region = db.Column(db.String(100))
    lead_investigator_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    cause_determination = db.Column(db.String(200))
    cause_description = db.Column(db.Text)
    origin = db.Column(db.String(200))
    status = db.Column(db.String(20), default="open")
    is_court_case = db.Column(db.Boolean, default=False)
    court_details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime)

    lead_investigator = db.relationship("User", backref="investigations", lazy=True)
    evidences = db.relationship("Evidence", backref="investigation", lazy=True)
    witness_statements = db.relationship("WitnessStatement", backref="investigation", lazy=True)


class Evidence(db.Model):
    __tablename__ = "evidences"
    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.Integer, db.ForeignKey("investigations.id"), nullable=False)
    evidence_no = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text, nullable=False)
    evidence_type = db.Column(db.String(50))
    location_found = db.Column(db.String(200))
    collected_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    collected_at = db.Column(db.DateTime)
    storage_location = db.Column(db.String(100))
    chain_of_custody = db.Column(db.Text)
    file_path = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WitnessStatement(db.Model):
    __tablename__ = "witness_statements"
    id = db.Column(db.Integer, primary_key=True)
    investigation_id = db.Column(db.Integer, db.ForeignKey("investigations.id"), nullable=False)
    witness_name = db.Column(db.String(200), nullable=False)
    witness_contact = db.Column(db.String(100))
    statement = db.Column(db.Text, nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    signed = db.Column(db.Boolean, default=False)


# ─── Module 5: Public Service Portal ──────────────────


class PublicComplaint(db.Model):
    __tablename__ = "public_complaints"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    complaint_type = db.Column(db.String(50))
    region = db.Column(db.String(100))
    status = db.Column(db.String(20), default="submitted")
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    resolution = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)


class HazardReport(db.Model):
    __tablename__ = "hazard_reports"
    id = db.Column(db.Integer, primary_key=True)
    reporter_name = db.Column(db.String(200))
    reporter_email = db.Column(db.String(120))
    reporter_phone = db.Column(db.String(20))
    location = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, nullable=False)
    hazard_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default="reported")
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    action_taken = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)


class TrainingRegistration(db.Model):
    __tablename__ = "training_registrations"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"))
    full_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    organization = db.Column(db.String(200))
    status = db.Column(db.String(20), default="registered")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Module 6: Human Resource Management ──────────────────


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("User", foreign_keys=[user_id], backref="leave_requests", lazy=True)
    approver = db.relationship("User", foreign_keys=[approved_by], lazy=True)


class Attendance(db.Model):
    __tablename__ = "attendance"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    status = db.Column(db.String(20))

    user = db.relationship("User", backref="attendance_records", lazy=True)


class PerformanceEvaluation(db.Model):
    __tablename__ = "performance_evaluations"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    evaluator_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    review_period = db.Column(db.String(50))
    rating = db.Column(db.Integer)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    employee = db.relationship("User", foreign_keys=[user_id], backref="evaluations", lazy=True)
    evaluator = db.relationship("User", foreign_keys=[evaluator_id], lazy=True)


# ─── Module 7: Training Management ──────────────────


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    photo = db.Column(db.String(500))
    description = db.Column(db.Text)
    duration_hours = db.Column(db.Integer)
    max_participants = db.Column(db.Integer)
    instructor_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="upcoming")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    instructor = db.relationship("User", backref="courses_teaching", lazy=True)
    enrollments = db.relationship("CourseEnrollment", backref="course", lazy=True)
    exams = db.relationship("Exam", backref="course", lazy=True)


class CourseEnrollment(db.Model):
    __tablename__ = "course_enrollments"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(20), default="enrolled")
    completed_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="enrollments", lazy=True)


class Exam(db.Model):
    __tablename__ = "exams"
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    passing_score = db.Column(db.Integer, default=70)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    results = db.relationship("ExamResult", backref="exam", lazy=True)


class ExamResult(db.Model):
    __tablename__ = "exam_results"
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    score = db.Column(db.Integer)
    passed = db.Column(db.Boolean)
    taken_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="exam_results", lazy=True)


class Certification(db.Model):
    __tablename__ = "certifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    cert_name = db.Column(db.String(200), nullable=False)
    issuing_body = db.Column(db.String(200))
    issue_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    cert_file = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="certifications", lazy=True)


# ─── Module 8: Fleet Management ──────────────────


class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    registration_no = db.Column(db.String(50), unique=True, nullable=False)
    vehicle_type = db.Column(db.String(50))
    photo = db.Column(db.String(500))
    make = db.Column(db.String(100))
    model = db.Column(db.String(100))
    year = db.Column(db.Integer)
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id"))
    status = db.Column(db.String(20), default="available")
    fuel_type = db.Column(db.String(20))
    tank_capacity = db.Column(db.Float)
    mileage = db.Column(db.Float)
    insurance_expiry = db.Column(db.Date)
    road_tax_expiry = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    maintenance_records = db.relationship("MaintenanceRecord", backref="vehicle", lazy=True)
    fuel_logs = db.relationship("FuelLog", backref="vehicle", lazy=True)


class MaintenanceRecord(db.Model):
    __tablename__ = "maintenance_records"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    maintenance_type = db.Column(db.String(50))
    description = db.Column(db.Text)
    cost = db.Column(db.Float)
    service_provider = db.Column(db.String(200))
    scheduled_date = db.Column(db.Date)
    completed_date = db.Column(db.Date)
    status = db.Column(db.String(20), default="scheduled")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FuelLog(db.Model):
    __tablename__ = "fuel_logs"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    liters = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float)
    station_name = db.Column(db.String(200))
    refuel_date = db.Column(db.DateTime, default=datetime.utcnow)
    mileage = db.Column(db.Float)

    driver = db.relationship("User", backref="fuel_logs", lazy=True)


# ─── Module 9: Asset Management ──────────────────


class Asset(db.Model):
    __tablename__ = "assets"
    id = db.Column(db.Integer, primary_key=True)
    asset_tag = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id"))
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.id"))
    purchase_date = db.Column(db.Date)
    purchase_cost = db.Column(db.Float)
    current_value = db.Column(db.Float)
    depreciation_rate = db.Column(db.Float)
    barcode = db.Column(db.String(100))
    status = db.Column(db.String(20), default="active")
    location = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assigned_user = db.relationship("User", backref="assigned_assets", lazy=True)


class Procurement(db.Model):
    __tablename__ = "procurements"
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer)
    estimated_cost = db.Column(db.Float)
    actual_cost = db.Column(db.Float)
    vendor = db.Column(db.String(200))
    status = db.Column(db.String(20), default="requested")
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Module 10: Financial Management ──────────────────


class FeeCollection(db.Model):
    __tablename__ = "fee_collections"
    id = db.Column(db.Integer, primary_key=True)
    receipt_no = db.Column(db.String(50), unique=True, nullable=False)
    payer_name = db.Column(db.String(200), nullable=False)
    payer_email = db.Column(db.String(120))
    fee_type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50))
    transaction_id = db.Column(db.String(100))
    status = db.Column(db.String(20), default="pending")
    collected_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    collected_at = db.Column(db.DateTime, default=datetime.utcnow)
    certificate_id = db.Column(db.Integer, db.ForeignKey("fire_certificates.id"))


class Budget(db.Model):
    __tablename__ = "budgets"
    id = db.Column(db.Integer, primary_key=True)
    fiscal_year = db.Column(db.Integer, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    allocated_amount = db.Column(db.Float)
    spent_amount = db.Column(db.Float, default=0)
    remaining = db.Column(db.Float)
    notes = db.Column(db.Text)


class FinancialTransaction(db.Model):
    __tablename__ = "financial_transactions"
    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100))
    reference = db.Column(db.String(100))
    initiated_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ─── Module 11: Document Management ──────────────────


class Document(db.Model):
    __tablename__ = "documents"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50))
    file_name = db.Column(db.String(255))
    file_path = db.Column(db.String(500))
    file_size = db.Column(db.Integer)
    file_type = db.Column(db.String(50))
    version = db.Column(db.Integer, default=1)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_archived = db.Column(db.Boolean, default=False)
    access_level = db.Column(db.String(20), default="internal")
    signature_data = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    uploader = db.relationship("User", backref="uploaded_documents", lazy=True)


# ─── Module 12: Station Operations ──────────────────


class DutyRoster(db.Model):
    __tablename__ = "duty_rosters"
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    shift_date = db.Column(db.Date, nullable=False)
    shift_type = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    role = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    personnel = db.relationship("User", foreign_keys=[user_id], backref="duty_shifts", lazy=True)


class OccurrenceLog(db.Model):
    __tablename__ = "occurrence_logs"
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.Integer, db.ForeignKey("stations.id"), nullable=False)
    log_date = db.Column(db.Date, nullable=False, default=date.today)
    entry_no = db.Column(db.Integer)
    time = db.Column(db.Time)
    description = db.Column(db.Text, nullable=False)
    incident_type = db.Column(db.String(50))
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    recorder = db.relationship("User", backref="occurrence_logs", lazy=True)


# ─── Module 13: Disaster Management ──────────────────


class DisasterEvent(db.Model):
    __tablename__ = "disaster_events"
    id = db.Column(db.Integer, primary_key=True)
    event_no = db.Column(db.String(50), unique=True, nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(300), nullable=False)
    region = db.Column(db.String(100))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20))
    status = db.Column(db.String(20), default="active")
    declared_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    declared_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)

    deployments = db.relationship("DisasterDeployment", backref="event", lazy=True)


class DisasterDeployment(db.Model):
    __tablename__ = "disaster_deployments"
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("disaster_events.id"), nullable=False)
    resource_type = db.Column(db.String(50))
    identifier = db.Column(db.String(100))
    quantity = db.Column(db.Integer)
    deployed_to = db.Column(db.String(200))
    deployed_at = db.Column(db.DateTime, default=datetime.utcnow)
    recovered_at = db.Column(db.DateTime)


class Shelter(db.Model):
    __tablename__ = "shelters"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    region = db.Column(db.String(100))
    address = db.Column(db.Text)
    capacity = db.Column(db.Integer)
    current_occupants = db.Column(db.Integer, default=0)
    contact = db.Column(db.String(20))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    status = db.Column(db.String(20), default="available")


# ─── Module 14: GIS & Mapping ──────────────────


class Hydrant(db.Model):
    __tablename__ = "hydrants"
    id = db.Column(db.Integer, primary_key=True)
    hydrant_no = db.Column(db.String(50), unique=True, nullable=False)
    location = db.Column(db.String(300))
    region = db.Column(db.String(100))
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="active")
    flow_rate = db.Column(db.Float)
    last_inspected = db.Column(db.Date)
    notes = db.Column(db.Text)


class RiskZone(db.Model):
    __tablename__ = "risk_zones"
    id = db.Column(db.Integer, primary_key=True)
    zone_name = db.Column(db.String(200), nullable=False)
    region = db.Column(db.String(100))
    risk_level = db.Column(db.String(20))
    boundary_data = db.Column(db.Text)
    population_density = db.Column(db.Integer)
    notes = db.Column(db.Text)


# ─── Audit Log ──────────────────


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50))
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
