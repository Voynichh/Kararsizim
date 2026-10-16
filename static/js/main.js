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
    li.setAttribute("data-option-id", String(option.id));

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
  function bindVoteForm(form) {
    if (form.hasAttribute("data-bound")) {
      return;
    }
    form.setAttribute("data-bound", "");
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
      // Anında geri bildirim: seçilen düğme hemen vurgulanır, sunucu yanıtı gelince sonuçlar açılır.
      submitter.classList.add("option--chosen");
      form.classList.add("vote-form--busy");

      function fallback() {
        submitter.classList.remove("option--chosen");
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
  }

  function initVoteForms() {
    document.querySelectorAll("[data-vote-form]").forEach(bindVoteForm);
  }

  // Canlı güncelleme: sayfadaki anketlerin sayıları birkaç saniyede bir yenilenir (F5 gerekmez).
  // Seçenek bazlı sonuçları sunucu yalnızca oy vermiş kişiye ve anket sahibine gönderir.
  function updateCard(card, data) {
    var changed = false;
    var total = card.querySelector("[data-total-votes]");
    if (total && typeof data.total_votes === "number") {
      var totalText = data.total_votes + " oy";
      if (total.textContent !== totalText) {
        total.textContent = totalText;
        changed = true;
      }
    }
    if (!data.options || !card.querySelector("[data-results]")) {
      return changed;
    }
    var maxVotes = data.options.reduce(function (max, option) {
      return Math.max(max, option.votes);
    }, 0);
    data.options.forEach(function (option) {
      var item = card.querySelector('.result[data-option-id="' + option.id + '"]');
      if (!item) {
        return;
      }
      item.setAttribute("data-percent", String(option.percent));
      item.classList.toggle("result--top", maxVotes > 0 && option.votes === maxVotes);
      var stat = item.querySelector(".result__stat");
      var statText = "%" + option.percent + " · " + option.votes + " oy";
      if (stat && stat.textContent !== statText) {
        stat.textContent = statText;
        changed = true;
      }
      var bar = item.querySelector(".result__bar");
      if (bar) {
        bar.style.width = option.percent + "%";
      }
    });
    return changed;
  }

  // Silinen anketin kartı kaldırılır (detay sayfasında kısa bir bilgi gösterilir).
  function removeCard(card) {
    if (card.querySelector(".vote-form--busy")) {
      return;
    }
    if (card.closest(".feed")) {
      card.remove();
      return;
    }
    var notice = document.createElement("section");
    notice.className = "card";
    var text = document.createElement("p");
    text.textContent = "Bu anket silindi.";
    notice.appendChild(text);
    card.replaceWith(notice);
  }

  function initLiveResults() {
    var source = document.querySelector("[data-live-url]");
    if (!source || !window.fetch) {
      return;
    }
    var url = source.getAttribute("data-live-url");
    var feed = document.querySelector(".feed[data-feed-live]");
    var cardsUrl = feed ? feed.getAttribute("data-cards-url") : null;
    // Sunucu çağrısı (Vercel kotası) tasarrufu: 10 sn ile başlar, değişiklik yoksa 30 sn'ye kadar
    // seyrekleşir, hata olursa 60 sn'ye kadar uzar; 2 dakika etkileşim olmazsa tamamen durur.
    var BASE_DELAY = 10000;
    var QUIET_MAX_DELAY = 30000;
    var MAX_DELAY = 60000;
    var IDLE_AFTER = 120000;
    var delay = BASE_DELAY;
    var lastActivity = Date.now();
    var stopped = false;
    var timer = null;
    var busy = false;
    var seenMax = 0; // bilinen en büyük anket id'si (daha büyükler "yeni" sayılır)
    var pending = []; // sayfa başında değilken bekleyen yeni anket id'leri
    var banner = null;

    function domMaxId() {
      var max = 0;
      document.querySelectorAll(".poll-card[data-poll-id]").forEach(function (card) {
        max = Math.max(max, parseInt(card.getAttribute("data-poll-id"), 10) || 0);
      });
      return max;
    }
    seenMax = domMaxId();

    // Kullanıcı etkileşimi: durmuşsa yoklama hemen yeniden başlar.
    function noteActivity() {
      lastActivity = Date.now();
      if (stopped) {
        stopped = false;
        delay = BASE_DELAY;
        window.clearTimeout(timer);
        tick();
      }
    }
    ["pointerdown", "keydown", "scroll", "touchstart"].forEach(function (name) {
      window.addEventListener(name, noteActivity, { passive: true });
    });

    function schedule() {
      window.clearTimeout(timer);
      timer = window.setTimeout(tick, delay);
    }

    function hideBanner() {
      if (banner) {
        banner.remove();
        banner = null;
      }
    }

    function showBanner() {
      if (!banner) {
        banner = document.createElement("button");
        banner.type = "button";
        banner.className = "btn btn--primary btn--block new-polls";
        banner.addEventListener("click", function () {
          window.scrollTo(0, 0);
          insertPending();
        });
        feed.parentNode.insertBefore(banner, feed);
      }
      banner.textContent =
        pending.length === 1 ? "1 yeni anket · Göster" : pending.length + " yeni anket · Göster";
    }

    // Yeni kartlar sunucudan HTML parçası olarak alınır (kullanıcı metni orada kaçışlanmıştır) ve
    // DOMParser ile ayrıştırılıp düğümler olarak (metin olarak değil) akışın başına eklenir.
    function insertPending() {
      if (!pending.length || busy) {
        return;
      }
      var ids = pending.slice(0, 20);
      busy = true;
      window
        .fetch(cardsUrl + "?ids=" + ids.join(","), {
          headers: { Accept: "text/html" },
          credentials: "same-origin",
        })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("cards failed");
          }
          return response.text();
        })
        .then(function (html) {
          var doc = new DOMParser().parseFromString(html, "text/html");
          var fresh = Array.prototype.slice.call(doc.querySelectorAll(".poll-card"));
          var anchor = feed.firstChild;
          fresh.forEach(function (card) {
            var id = card.getAttribute("data-poll-id");
            if (feed.querySelector('.poll-card[data-poll-id="' + id + '"]')) {
              return;
            }
            var node = document.importNode(card, true);
            feed.insertBefore(node, anchor);
            node.querySelectorAll("[data-vote-form]").forEach(bindVoteForm);
            fillBars(node);
          });
          var empty = document.querySelector("[data-empty-state]");
          if (empty && fresh.length) {
            empty.remove();
          }
          pending = pending.filter(function (id) {
            return ids.indexOf(id) === -1;
          });
          if (!pending.length) {
            hideBanner();
          } else {
            showBanner();
          }
        })
        .catch(function () {
          delay = Math.min(delay * 2, MAX_DELAY);
        })
        .then(function () {
          busy = false;
        });
    }

    function handleNewIds(newIds) {
      newIds.forEach(function (id) {
        seenMax = Math.max(seenMax, id);
        var key = String(id);
        if (pending.indexOf(key) === -1 && !document.querySelector('.poll-card[data-poll-id="' + key + '"]')) {
          pending.push(key);
        }
      });
      if (!pending.length) {
        return;
      }
      // Sayfanın başındaysa kartlar kendiliğinden eklenir; aşağıda okuyorsa kayma olmasın diye
      // sabit bir "yeni anket" düğmesi gösterilir.
      if (window.scrollY < 120) {
        window.setTimeout(insertPending, 0);
      } else {
        showBanner();
      }
    }

    function tick() {
      if (Date.now() - lastActivity > IDLE_AFTER) {
        stopped = true; // etkileşim olunca noteActivity() yeniden başlatır
        return;
      }
      if (document.hidden || busy) {
        schedule();
        return;
      }
      var cards = {};
      var ids = [];
      document.querySelectorAll(".poll-card[data-poll-id]").forEach(function (card) {
        var id = card.getAttribute("data-poll-id");
        if (!cards[id] && ids.length < 20) {
          cards[id] = card;
          ids.push(id);
        }
      });
      if (!ids.length && !feed) {
        return;
      }
      var query = "?ids=" + ids.join(",");
      if (feed) {
        query += "&after=" + Math.max(seenMax, domMaxId());
      }
      busy = true;
      window
        .fetch(url + query, {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        })
        .then(function (response) {
          if (!response.ok) {
            throw new Error("live failed");
          }
          return response.json();
        })
        .then(function (data) {
          if (!data || data.ok !== true) {
            throw new Error("live failed");
          }
          var alive = {};
          var changed = false;
          data.polls.forEach(function (item) {
            alive[String(item.id)] = true;
            // Oy verme sürerken (form meşgulken) o kartın sayıları ezilmez.
            var card = cards[String(item.id)];
            if (card && !card.querySelector(".vote-form--busy")) {
              if (updateCard(card, item)) {
                changed = true;
              }
            }
          });
          // İstenip de dönmeyen anket silinmiştir.
          ids.forEach(function (id) {
            if (!alive[id]) {
              removeCard(cards[id]);
              changed = true;
            }
          });
          if (feed && data.new_ids && data.new_ids.length) {
            handleNewIds(data.new_ids);
            changed = true;
          }
          // Hareket varsa hızlı, yoksa giderek seyrek.
          delay = changed ? BASE_DELAY : Math.min(Math.round(delay * 1.5), QUIET_MAX_DELAY);
        })
        .catch(function () {
          // Hata olursa seyrekleştir; sayfa yine de çalışır.
          delay = Math.min(delay * 2, MAX_DELAY);
        })
        .then(function () {
          busy = false;
          schedule();
        });
    }

    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) {
        lastActivity = Date.now();
        stopped = false;
        delay = BASE_DELAY;
        window.clearTimeout(timer);
        tick();
      }
    });
    schedule();
  }

  // "Linki kopyala": yalnızca Pano API'si varsa gösterilir (yoksa düğme gizli kalır).
  function initCopyLink() {
    var button = document.querySelector("[data-copy-link]");
    if (!button || !navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }
    var label = button.textContent;
    button.hidden = false;
    button.addEventListener("click", function () {
      // Sorgu dizisi ve parça (#...) olmadan, yalnızca anketin adresi.
      var url = window.location.origin + window.location.pathname;
      navigator.clipboard.writeText(url).then(
        function () {
          button.textContent = "Kopyalandı ✓";
          window.setTimeout(function () {
            button.textContent = label;
          }, 2000);
        },
        function () {
          button.textContent = "Kopyalanamadı";
          window.setTimeout(function () {
            button.textContent = label;
          }, 2000);
        }
      );
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initToasts();
    initOptionList();
    fillBars(document);
    initVoteForms();
    initLiveResults();
    initCopyLink();
  });
})();
