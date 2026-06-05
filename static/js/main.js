document.addEventListener('DOMContentLoaded', function () {
  var alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      var bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000);
  });

  document.querySelectorAll('form').forEach(function (form) {
    var submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      form.addEventListener('submit', function () {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Processing...';
      });
    }
  });
});
