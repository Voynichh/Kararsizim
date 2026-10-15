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

  // Sonuç çubuklarının genişliği data-percent değerinden ayarlanır (CSP gereği inline stil yok).
  function fillBars(root) {
    var results = root.querySelectorAll(".result[data-percent]");
    results.forEach(function (result) {
      var bar = result.querySelector(".result__bar");
      var percent = parseInt(result.getAttribute("data-percent"), 10) || 0;
      if (!bar) {
        return;
      }
      bar.style.width = "0%";
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
          bar.style.width = percent + "%";
        });
      });
    });
  }

  // Kullanıcıdan gelen metinler yalnızca textContent / createTextNode ile DOM'a yazılır.
  function buildResult(option, selectedId, maxVotes) {
    var li = document.createElement("li");
    li.className = "result";
    if (option.id === selectedId) {
      li.classList.add("result--mine");
    }
    if (maxVotes > 0 && option.votes === maxVotes) {
      li.classList.add("result--top");
    }
    li.setAttribute("data-percent", String(option.percent));

    var bar = document.createElement("span");
    bar.className = "result__bar";
    bar.setAttribute("aria-hidden", "true");

    var label = document.createElement("span");
    label.className = "result__label";
    label.appendChild(document.createTextNode(option.text));
    if (option.id === selectedId) {
      label.appendChild(document.createTextNode(" "));
      var badge = document.createElement("span");
      badge.className = "result__badge";
      badge.textContent = "✓ senin oyun";
      label.appendChild(badge);
    }

    var stat = document.createElement("span");
    stat.className = "result__stat";
    stat.textContent = "%" + option.percent + " · " + option.votes + " oy";

    li.appendChild(bar);
    li.appendChild(label);
    li.appendChild(stat);
    return li;
  }

  function showResults(form, data) {
    var card = form.closest(".poll-card");
    var list = document.createElement("ul");
    list.className = "option-list";
    list.setAttribute("data-results", "");
    var maxVotes = data.options.reduce(function (max, option) {
      return Math.max(max, option.votes);
    }, 0);
    data.options.forEach(function (option) {
      list.appendChild(buildResult(option, data.selected_option_id, maxVotes));
    });
    form.replaceWith(list);
    var total = card.querySelector("[data-total-votes]");
    if (total) {
      total.textContent = data.total_votes + " oy";
    }
    fillBars(card);
  }

  // Fetch ile oy verme. Her türlü hatada normal form gönderimine düşülür.
  function initVoteForms() {
    document.querySelectorAll("[data-vote-form]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.hasAttribute("data-no-ajax") || !window.fetch || !window.FormData) {
          return;
        }
        var submitter = event.submitter;
        if (!submitter || !submitter.name) {
          return;
        }
        event.preventDefault();
        var body = new URLSearchParams(new FormData(form, submitter));
        form.classList.add("vote-form--busy");

        function fallback() {
          form.classList.remove("vote-form--busy");
          form.setAttribute("data-no-ajax", "");
          form.requestSubmit(submitter);
        }

        window
          .fetch(form.getAttribute("action"), {
            method: "POST",
            body: body,
            headers: { Accept: "application/json" },
            credentials: "same-origin",
          })
          .then(function (response) {
            if (!response.ok) {
              throw new Error("vote failed");
            }
            return response.json();
          })
          .then(function (data) {
            if (!data || data.ok !== true) {
              throw new Error("vote failed");
            }
            showResults(form, data);
          })
          .catch(fallback);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initToasts();
    initOptionList();
    fillBars(document);
    initVoteForms();
  });
})();
