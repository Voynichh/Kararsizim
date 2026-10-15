// kararsızım — ilerletici iyileştirme. JS kapalıyken de her şey çalışmalıdır.
(function () {
  "use strict";

  // Toast mesajlarını birkaç saniye sonra gizle.
  function initToasts() {
    var toasts = document.querySelectorAll("[data-toast]");
    toasts.forEach(function (toast) {
      window.setTimeout(function () {
        toast.classList.add("toast--hide");
        window.setTimeout(function () {
          toast.remove();
        }, 400);
      }, 5000);
    });
  }

  document.addEventListener("DOMContentLoaded", initToasts);
})();
