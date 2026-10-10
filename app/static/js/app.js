(function () {
  'use strict';

  var toggle = document.getElementById('nav-toggle');
  var sidebar = document.getElementById('sidebar');
  if (toggle && sidebar) {
    toggle.addEventListener('click', function () {
      var open = sidebar.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  var dialog = document.getElementById('confirm-dialog');
  var pending = null;
  var supportsDialog = dialog && typeof dialog.showModal === 'function';

  document.addEventListener('submit', function (event) {
    var form = event.target;
    var message = form.getAttribute && form.getAttribute('data-confirm');
    if (!message || form.getAttribute('data-confirmed') === '1') { return; }
    event.preventDefault();
    if (!supportsDialog) {
      if (window.confirm(message)) { form.setAttribute('data-confirmed', '1'); form.submit(); }
      return;
    }
    pending = form;
    dialog.querySelector('[data-confirm-message]').textContent = message;
    dialog.showModal();
    dialog.querySelector('[data-confirm-cancel]').focus();
  });

  if (supportsDialog) {
    dialog.querySelector('[data-confirm-accept]').addEventListener('click', function () {
      var form = pending; pending = null; dialog.close();
      if (form) { form.setAttribute('data-confirmed', '1'); form.submit(); }
    });
    dialog.querySelector('[data-confirm-cancel]').addEventListener('click', function () {
      pending = null; dialog.close();
    });
    dialog.addEventListener('cancel', function () { pending = null; });
  }
})();
