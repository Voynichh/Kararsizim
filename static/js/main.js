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

  // Anket formunda seçenek ekle/kaldır (2–5). JS yoksa 5 alan da görünür kalır.
  function initOptionList() {
    var list = document.querySelector("[data-option-list]");
    if (!list) {
      return;
    }
    var items = Array.prototype.slice.call(list.querySelectorAll("[data-option-item]"));
    var addButton = list.querySelector("[data-add-option]");
    var min = parseInt(list.getAttribute("data-min"), 10) || 2;
    var max = items.length;

    function inputOf(item) {
      return item.querySelector("input");
    }

    var visible = min;
    items.forEach(function (item, index) {
      if (inputOf(item).value !== "" || item.hasAttribute("data-has-error")) {
        visible = Math.max(visible, index + 1);
      }
    });

    function render() {
      items.forEach(function (item, index) {
        item.hidden = index >= visible;
        var removeButton = item.querySelector("[data-remove-option]");
        if (removeButton) {
          removeButton.hidden = index >= visible || index < min;
        }
      });
      addButton.hidden = visible >= max;
    }

    addButton.addEventListener("click", function () {
      if (visible < max) {
        visible += 1;
        render();
        inputOf(items[visible - 1]).focus();
      }
    });

    items.forEach(function (item, index) {
      var removeButton = item.querySelector("[data-remove-option]");
      if (!removeButton) {
        return;
      }
      removeButton.addEventListener("click", function () {
        // Sonraki alanların değerlerini yukarı kaydır, sondaki alanı gizle.
        for (var i = index; i < visible - 1; i += 1) {
          inputOf(items[i]).value = inputOf(items[i + 1]).value;
        }
        inputOf(items[visible - 1]).value = "";
        visible -= 1;
        render();
        addButton.focus();
      });
    });

    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    initToasts();
    initOptionList();
  });
})();
