/* ==========================================================================
   Voltiq storefront behaviour
   - CSRF-aware fetch helpers
   - Toasts, drawer, popovers, search suggestions
   - AJAX cart, wishlist, catalog filtering and newsletter
   ========================================================================== */
(function () {
  "use strict";

  const body = document.body;
  const CFG = window.VOLTIQ_CONFIG || {};

  /* ---------------------------------------------------------------------
     Utilities
     --------------------------------------------------------------------- */
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  function csrfToken() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.content) || getCookie("csrftoken");
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  async function request(url, options = {}) {
    const opts = Object.assign({ method: "POST", headers: {} }, options);
    opts.headers = Object.assign({ "X-Requested-With": "XMLHttpRequest" }, opts.headers);
    if (opts.method !== "GET") {
      opts.headers["X-CSRFToken"] = csrfToken();
    }
    if (opts.json) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
      delete opts.json;
    }
    const response = await fetch(url, opts);
    let data = {};
    const contentType = response.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await response.json().catch(() => ({}));
    } else {
      data = { html: await response.text() };
    }
    if (!response.ok) {
      const error = new Error(data.message || "Something went wrong. Please try again.");
      error.data = data;
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function formatMoney(value) {
    return "Rs. " + Number(value || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }

  /* ---------------------------------------------------------------------
     Toasts
     --------------------------------------------------------------------- */
  const ICONS = {
    success: '<svg class="icon" aria-hidden="true"><use href="#i-check-circle"></use></svg>',
    error: '<svg class="icon" aria-hidden="true"><use href="#i-alert-circle"></use></svg>',
    warning: '<svg class="icon" aria-hidden="true"><use href="#i-alert-circle"></use></svg>',
    info: '<svg class="icon" aria-hidden="true"><use href="#i-info"></use></svg>',
  };

  function toast(message, type = "info", timeout = 4200) {
    const stack = document.getElementById("toast-stack");
    if (!stack) return;
    const el = document.createElement("div");
    el.className = "toast toast-" + type;
    el.setAttribute("data-toast", "");
    el.innerHTML =
      '<span class="toast-icon">' + (ICONS[type] || ICONS.info) + "</span>" +
      '<div class="toast-content">' + escapeHtml(message) + "</div>" +
      '<button class="toast-close" type="button" data-toast-close aria-label="Dismiss notification">' +
      '<svg class="icon" aria-hidden="true"><use href="#i-x"></use></svg></button>';
    stack.appendChild(el);
    const dismiss = () => {
      el.classList.add("is-leaving");
      setTimeout(() => el.remove(), 220);
    };
    el.querySelector("[data-toast-close]").addEventListener("click", dismiss);
    if (timeout) setTimeout(dismiss, timeout);
  }
  window.voltiqToast = toast;

  document.querySelectorAll("[data-toast]").forEach((el) => {
    const close = el.querySelector("[data-toast-close]");
    if (close) {
      close.addEventListener("click", () => {
        el.classList.add("is-leaving");
        setTimeout(() => el.remove(), 220);
      });
    }
    setTimeout(() => {
      el.classList.add("is-leaving");
      setTimeout(() => el.remove(), 220);
    }, 6000);
  });

  /* ---------------------------------------------------------------------
     Header: scroll shadow, drawer, popovers
     --------------------------------------------------------------------- */
  const header = document.getElementById("site-header");
  if (header) {
    const onScroll = () => header.classList.toggle("is-scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  const drawer = document.getElementById("mobile-drawer");
  const backdrop = document.querySelector(".drawer-backdrop");

  function openDrawer() {
    if (!drawer) return;
    drawer.classList.add("is-open");
    drawer.setAttribute("aria-hidden", "false");
    if (backdrop) backdrop.hidden = false;
    body.classList.add("no-scroll");
    const first = drawer.querySelector("button, a, input");
    if (first) setTimeout(() => first.focus(), 120);
  }

  function closeDrawer() {
    if (!drawer) return;
    drawer.classList.remove("is-open");
    drawer.setAttribute("aria-hidden", "true");
    if (backdrop) backdrop.hidden = true;
    body.classList.remove("no-scroll");
  }

  document.querySelectorAll("[data-drawer-open]").forEach((btn) => btn.addEventListener("click", openDrawer));
  document.querySelectorAll("[data-drawer-close]").forEach((btn) => btn.addEventListener("click", closeDrawer));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDrawer();
      closeSearchPanel();
      closeFilters();
    }
  });

  document.querySelectorAll(".drawer-expand").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sub = btn.closest(".drawer-cat")?.nextElementSibling;
      if (!sub || !sub.classList.contains("drawer-sub")) return;
      const open = sub.hasAttribute("hidden");
      if (open) sub.removeAttribute("hidden");
      else sub.setAttribute("hidden", "");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });

  document.querySelectorAll("details.popover, details.user-menu").forEach((details) => {
    details.addEventListener("toggle", () => {
      if (!details.open) return;
      document.querySelectorAll("details.popover[open], details.user-menu[open]").forEach((other) => {
        if (other !== details) other.open = false;
      });
    });
  });
  document.addEventListener("click", (event) => {
    document.querySelectorAll("details.popover[open], details.user-menu[open]").forEach((details) => {
      if (!details.contains(event.target)) details.open = false;
    });
  });

  /* Mega menu keyboard support */
  document.querySelectorAll(".nav-mega-trigger").forEach((trigger) => {
    trigger.addEventListener("click", () => {
      const parent = trigger.closest(".nav-mega");
      const open = parent.classList.toggle("is-open");
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });

  /* ---------------------------------------------------------------------
     Live search suggestions
     --------------------------------------------------------------------- */
  const searchForm = document.getElementById("search-form");
  const searchInput = document.getElementById("site-search");
  const searchPanel = document.getElementById("search-suggestions");
  let searchTimer = null;
  let searchAbort = null;
  let searchIndex = -1;

  function closeSearchPanel() {
    if (!searchPanel) return;
    searchPanel.hidden = true;
    searchPanel.innerHTML = "";
    searchIndex = -1;
    if (searchInput) searchInput.setAttribute("aria-expanded", "false");
  }

  function renderSearch(data) {
    if (!searchPanel) return;
    const products = data.products || [];
    const categories = data.categories || [];
    const brands = data.brands || [];
    if (!products.length && !categories.length && !brands.length) {
      searchPanel.innerHTML = '<div class="search-empty">No matches for “' + escapeHtml(data.query || "") + '”. Try a different keyword.</div>';
      searchPanel.hidden = false;
      return;
    }
    let html = "";
    if (products.length) {
      html += '<div class="search-block"><div class="search-block-title"><span>Products</span><span>' + products.length + " results</span></div>";
      html += products
        .map(
          (p) =>
            '<a class="search-result" href="' + escapeHtml(p.url) + '">' +
            (p.image
              ? '<img src="' + escapeHtml(p.image) + '" alt="" loading="lazy">'
              : '<span class="search-thumb"><svg class="icon"><use href="#i-laptop"></use></svg></span>') +
            '<span class="search-result-body"><strong>' + escapeHtml(p.name) + "</strong><small>" +
            escapeHtml(p.brand) + " · " + escapeHtml(p.category) + "</small></span>" +
            '<span class="search-result-price">' + escapeHtml(p.price) + "</span></a>"
        )
        .join("");
      html += "</div>";
    }
    if (categories.length || brands.length) {
      html += '<div class="search-block"><div class="search-block-title"><span>Browse</span></div>';
      html += categories
        .map((c) => '<a class="search-result" href="' + escapeHtml(c.url) + '"><span class="search-thumb"><svg class="icon"><use href="#i-grid"></use></svg></span><span class="search-result-body"><strong>' + escapeHtml(c.name) + "</strong><small>Category</small></span></a>")
        .join("");
      html += brands
        .map((b) => '<a class="search-result" href="' + escapeHtml(b.url) + '"><span class="search-thumb"><svg class="icon"><use href="#i-tag"></use></svg></span><span class="search-result-body"><strong>' + escapeHtml(b.name) + "</strong><small>Brand</small></span></a>")
        .join("");
      html += "</div>";
    }
    html += '<div class="search-block"><a class="search-result" href="' + escapeHtml(data.all_url) + '"><span class="search-thumb"><svg class="icon"><use href="#i-search"></use></svg></span><span class="search-result-body"><strong>See all results for “' + escapeHtml(data.query) + "”</strong></span></a></div>";
    searchPanel.innerHTML = html;
    searchPanel.hidden = false;
    if (searchInput) searchInput.setAttribute("aria-expanded", "true");
    searchIndex = -1;
  }

  if (searchInput && searchPanel && CFG.suggestions) {
    searchInput.addEventListener("input", () => {
      const query = searchInput.value.trim();
      clearTimeout(searchTimer);
      if (query.length < 2) {
        closeSearchPanel();
        return;
      }
      searchTimer = setTimeout(async () => {
        if (searchAbort) searchAbort.abort();
        searchAbort = new AbortController();
        searchPanel.hidden = false;
        searchPanel.innerHTML = '<div class="search-loading">Searching Voltiq…</div>';
        try {
          const response = await fetch(CFG.suggestions + "?q=" + encodeURIComponent(query), {
            signal: searchAbort.signal,
            headers: { "X-Requested-With": "XMLHttpRequest" },
          });
          if (!response.ok) throw new Error("search failed");
          renderSearch(await response.json());
        } catch (error) {
          if (error.name !== "AbortError") closeSearchPanel();
        }
      }, 220);
    });

    searchInput.addEventListener("focus", () => {
      if (searchInput.value.trim().length >= 2 && searchPanel.innerHTML) searchPanel.hidden = false;
    });

    searchInput.addEventListener("keydown", (event) => {
      const results = Array.from(searchPanel.querySelectorAll(".search-result"));
      if (!results.length) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        searchIndex = (searchIndex + 1) % results.length;
        results[searchIndex].focus();
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        searchIndex = (searchIndex - 1 + results.length) % results.length;
        results[searchIndex].focus();
      } else if (event.key === "Escape") {
        closeSearchPanel();
      }
    });

    document.addEventListener("click", (event) => {
      if (!searchPanel.contains(event.target) && event.target !== searchInput) closeSearchPanel();
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "/" && document.activeElement !== searchInput && !/input|textarea|select/i.test(document.activeElement.tagName)) {
        event.preventDefault();
        searchInput.focus();
      }
    });
  }
  if (searchForm) {
    searchForm.addEventListener("submit", () => closeSearchPanel());
  }

  /* ---------------------------------------------------------------------
     Cart and wishlist AJAX
     --------------------------------------------------------------------- */
  function bumpBadge(el, value) {
    if (!el) return;
    el.textContent = value;
    el.classList.toggle("is-zero", Number(value) === 0);
    el.classList.remove("is-bump");
    void el.offsetWidth;
    el.classList.add("is-bump");
  }

  function syncCart(data) {
    if (data.cart_count !== undefined) {
      ["cart-count", "cart-count-mobile"].forEach((id) => {
        const badge = document.getElementById(id);
        if (badge) bumpBadge(badge, data.cart_count);
      });
    }
    const map = {
      "[data-cart-subtotal]": data.subtotal_display,
      "[data-cart-discount]": data.discount_display,
      "[data-cart-shipping]": data.shipping_display,
      "[data-cart-total]": data.total_display,
    };
    Object.entries(map).forEach(([selector, value]) => {
      if (value === undefined) return;
      document.querySelectorAll(selector).forEach((el) => (el.textContent = value));
    });
    document.querySelectorAll("[data-cart-coupon]").forEach((el) => (el.textContent = data.coupon || ""));
    const remaining = document.querySelector("[data-free-shipping-remaining]");
    if (remaining && data.free_shipping_remaining !== undefined) {
      remaining.textContent = data.free_shipping_remaining > 0
        ? "Add " + formatMoney(data.free_shipping_remaining) + " more for free delivery"
        : "You have unlocked free delivery";
    }
  }

  async function addToCart(button, productId, quantity) {
    if (button) {
      button.classList.add("is-loading");
      button.disabled = true;
    }
    try {
      const data = await request(CFG.cartAdd, 
        { json: { product_id: productId, quantity: quantity } }
      );
      syncCart(data);
      toast(data.message || "Added to your cart.", "success");
    } catch (error) {
      toast(error.message, "error");
      if (error.data && error.data.auth_required) {
        setTimeout(() => (window.location.href = error.data.login_url || "/accounts/login/"), 800);
      }
    } finally {
      if (button) {
        button.classList.remove("is-loading");
        button.disabled = false;
      }
    }
  }

  document.addEventListener("click", (event) => {
    const addBtn = event.target.closest("[data-add-to-cart]");
    if (addBtn) {
      event.preventDefault();
      const qtyInput = document.getElementById("pdp-qty");
      const quantity = Number(qtyInput ? qtyInput.value : addBtn.dataset.quantity || 1);
      addToCart(addBtn, addBtn.dataset.addToCart, quantity || 1);
      return;
    }

    const wishBtn = event.target.closest("[data-wishlist-toggle]");
    if (wishBtn) {
      event.preventDefault();
      toggleWishlist(wishBtn);
      return;
    }
  });

  async function toggleWishlist(button) {
    if (button.classList.contains("is-loading")) return;
    button.classList.add("is-loading");
    try {
      const data = await request(CFG.wishlistToggle, { json: { product_id: button.dataset.wishlistToggle } });
      const active = Boolean(data.added);
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.setAttribute("aria-label", active ? "Remove from wishlist" : "Save to wishlist");
      bumpBadge(document.getElementById("wishlist-count"), data.wishlist_count);
      bumpBadge(document.getElementById("wishlist-count-mobile"), data.wishlist_count);
      toast(data.message, active ? "success" : "info");
    } catch (error) {
      if (error.status === 401 && error.data && error.data.login_url) {
        toast(error.message, "warning");
        setTimeout(() => (window.location.href = error.data.login_url), 700);
      } else {
        toast(error.message, "error");
      }
    } finally {
      button.classList.remove("is-loading");
    }
  }

  /* Quantity steppers */
  document.addEventListener("click", (event) => {
    const step = event.target.closest("[data-qty-step]");
    if (!step) return;
    const wrapper = step.closest(".counter, .pdp-buy-row, [data-quantity-wrap]");
    const input = wrapper ? wrapper.querySelector("input[type='number'], input[data-qty-input]") : null;
    if (!input) return;
    const max = Number(input.max || 99);
    const min = Number(input.min || 1);
    const delta = Number(step.dataset.qtyStep);
    const next = Math.min(max, Math.max(min, Number(input.value || 1) + delta));
    if (next === Number(input.value)) return;
    input.value = next;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });

  /* Cart page updates */
  document.addEventListener("change", async (event) => {
    const input = event.target.closest("[data-cart-qty]");
    if (!input) return;
    const row = input.closest("[data-cart-row]");
    if (!row) return;
    const itemId = row.dataset.cartRow;
    const quantity = Math.max(1, Number(input.value || 1));
    input.disabled = true;
    try {
      const data = await request(CFG.cartUpdate.replace(/0\/$/, itemId + "/"), { json: { quantity } });
      syncCart(data);
      const unit = Number(row.dataset.unitPrice || 0);
      const line = row.querySelector("[data-line-total]");
      if (line) line.textContent = formatMoney(unit * quantity);
      toast(data.message || "Cart updated.", "success", 2200);
    } catch (error) {
      toast(error.message, "error");
      input.value = input.dataset.previous || 1;
    } finally {
      input.disabled = false;
      input.dataset.previous = input.value;
    }
  });

  document.querySelectorAll("[data-cart-qty]").forEach((input) => {
    input.dataset.previous = input.value;
  });

  document.addEventListener("click", async (event) => {
    const removeBtn = event.target.closest("[data-cart-remove]");
    if (!removeBtn) return;
    const row = removeBtn.closest("[data-cart-row]");
    if (!row) return;
    removeBtn.disabled = true;
    try {
      const data = await request(CFG.cartRemove.replace(/0\/$/, row.dataset.cartRow + "/"), { json: {} });
      syncCart(data);
      row.style.transition = "opacity .2s ease, transform .2s ease";
      row.style.opacity = "0";
      row.style.transform = "translateX(-10px)";
      setTimeout(() => {
        row.remove();
        if (!document.querySelector("[data-cart-row]")) window.location.reload();
      }, 200);
      toast(data.message || "Item removed.", "info", 2400);
    } catch (error) {
      toast(error.message, "error");
      removeBtn.disabled = false;
    }
  });

  async function cartAction(url, payload, successMessage) {
    const data = await request(url, { json: payload || {} });
    syncCart(data);
    toast(data.message || successMessage, "success");
    return data;
  }

  document.querySelectorAll("[data-coupon-apply]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = form.querySelector("input[name='code']");
      const button = form.querySelector("button[type='submit']");
      if (!input || !input.value.trim()) return;
      if (button) button.classList.add("is-loading");
      try {
        await cartAction(CFG.couponApply, { code: input.value.trim() });
        window.location.reload();
      } catch (error) {
        toast(error.message, "error");
      } finally {
        if (button) button.classList.remove("is-loading");
      }
    });
  });

  document.querySelectorAll("[data-coupon-remove]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.classList.add("is-loading");
      try {
        await cartAction(CFG.couponRemove, {}, "Coupon removed.");
        window.location.reload();
      } catch (error) {
        toast(error.message, "error");
        btn.classList.remove("is-loading");
      }
    });
  });

  /* ---------------------------------------------------------------------
     Catalog: AJAX filtering, sorting, pagination
     --------------------------------------------------------------------- */
  const filterForm = document.getElementById("filter-form");
  const results = document.getElementById("catalog-results");
  let catalogController = null;

  function syncFilterQuery() {
    if (!filterForm) return new URLSearchParams();
    const params = new URLSearchParams();
    new FormData(filterForm).forEach((value, key) => {
      if (String(value).trim() !== "") params.append(key, value);
    });
    params.delete("page");
    params.delete("partial");
    return params;
  }

  async function loadCatalog(url, push = true) {
    if (!results) return;
    if (catalogController) catalogController.abort();
    catalogController = new AbortController();
    results.classList.add("is-loading");
    results.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        signal: catalogController.signal,
      });
      if (!response.ok) throw new Error("Could not load products.");
      const html = await response.text();
      results.innerHTML = html;
      results.classList.remove("is-loading");
      results.setAttribute("aria-busy", "false");
      if (push) window.history.pushState({ catalog: true }, "", url);
      const count = document.querySelector("[data-total-results]");
      if (count && response.headers.get("X-Total-Count")) count.textContent = response.headers.get("X-Total-Count");
      closeFilters();
      const top = results.getBoundingClientRect().top + window.scrollY - 110;
      window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
    } catch (error) {
      if (error.name !== "AbortError") {
        toast("Could not update results. Please try again.", "error");
        results.classList.remove("is-loading");
      }
    }
  }

  if (filterForm && results) {
    filterForm.addEventListener("change", () => {
      const params = syncFilterQuery();
      loadCatalog(window.location.pathname + "?" + params.toString());
    });
    filterForm.addEventListener("submit", (event) => {
      event.preventDefault();
      const params = syncFilterQuery();
      loadCatalog(window.location.pathname + "?" + params.toString());
    });
    const sortSelect = document.getElementById("sort-select");
    if (sortSelect) {
      sortSelect.addEventListener("change", () => {
        const params = syncFilterQuery();
        params.set("sort", sortSelect.value);
        loadCatalog(window.location.pathname + "?" + params.toString());
      });
    }
    results.addEventListener("click", (event) => {
      const link = event.target.closest(".pagination a, [data-catalog-link]");
      if (!link || !link.href) return;
      event.preventDefault();
      loadCatalog(link.href);
    });
    window.addEventListener("popstate", () => loadCatalog(window.location.href, false));
  }

  const filterPanel = document.getElementById("filters-panel");
  function closeFilters() {
    if (!filterPanel) return;
    filterPanel.classList.remove("is-open");
    body.classList.remove("no-scroll");
  }
  document.querySelectorAll("[data-filter-open]").forEach((btn) =>
    btn.addEventListener("click", () => {
      if (!filterPanel) return;
      filterPanel.classList.add("is-open");
      body.classList.add("no-scroll");
    })
  );
  document.querySelectorAll("[data-filter-close]").forEach((btn) => btn.addEventListener("click", closeFilters));

  /* List/grid view toggle */
  const grid = document.getElementById("product-grid");
  document.querySelectorAll("[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (!grid) return;
      const list = btn.dataset.view === "list";
      grid.classList.toggle("is-list", list);
      document.querySelectorAll("[data-view]").forEach((b) => b.classList.toggle("is-active", b === btn));
      try {
        localStorage.setItem("voltiq_catalog_view", list ? "list" : "grid");
      } catch (e) {}
    });
  });
  if (grid) {
    try {
      if (localStorage.getItem("voltiq_catalog_view") === "list") {
        grid.classList.add("is-list");
        document.querySelectorAll("[data-view]").forEach((b) => b.classList.toggle("is-active", b.dataset.view === "list"));
      }
    } catch (e) {}
  }

  /* ---------------------------------------------------------------------
     Product detail: gallery, tabs, sticky add to cart
     --------------------------------------------------------------------- */
  const mainImage = document.getElementById("pdp-main-image");
  document.querySelectorAll("[data-gallery-thumb]").forEach((thumb) => {
    thumb.addEventListener("click", () => {
      if (!mainImage) return;
      const source = thumb.dataset.galleryThumb;
      if (source) mainImage.src = source;
      document.querySelectorAll("[data-gallery-thumb]").forEach((t) => t.classList.toggle("is-active", t === thumb));
    });
  });

  document.querySelectorAll("[data-tab]").forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      document.querySelectorAll("[data-tab]").forEach((t) => {
        t.classList.remove("is-active");
        t.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll("[data-tab-panel]").forEach((panel) => panel.classList.remove("is-active"));
      tab.classList.add("is-active");
      tab.setAttribute("aria-selected", "true");
      const panel = document.querySelector('[data-tab-panel="' + target + '"]');
      if (panel) panel.classList.add("is-active");
    });
  });

  /* ---------------------------------------------------------------------
     Newsletter
     --------------------------------------------------------------------- */
  document.querySelectorAll("[data-newsletter-form]").forEach((form) => {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = form.querySelector("button[type='submit']");
      const input = form.querySelector("input[name='email']");
      if (!input || !input.value.trim()) return;
      if (button) button.classList.add("is-loading");
      try {
        const data = await request(form.action, { body: new FormData(form) });
        toast(data.message || "You're subscribed!", "success");
        form.reset();
      } catch (error) {
        toast(error.message, "error");
      } finally {
        if (button) button.classList.remove("is-loading");
      }
    });
  });

  /* ---------------------------------------------------------------------
     Password visibility toggles
     --------------------------------------------------------------------- */
  document.querySelectorAll("[data-password-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById(btn.dataset.passwordToggle);
      if (!input) return;
      const showing = input.type === "text";
      input.type = showing ? "password" : "text";
      btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
      btn.classList.toggle("is-active", !showing);
    });
  });

  /* ---------------------------------------------------------------------
     Countdown timers
     --------------------------------------------------------------------- */
  document.querySelectorAll("[data-countdown]").forEach((container) => {
    const end = new Date(container.dataset.countdown).getTime();
    if (Number.isNaN(end)) return;
    const fields = {
      days: container.querySelector("[data-days]"),
      hours: container.querySelector("[data-hours]"),
      minutes: container.querySelector("[data-minutes]"),
      seconds: container.querySelector("[data-seconds]"),
    };
    const tick = () => {
      const diff = Math.max(0, end - Date.now());
      const days = Math.floor(diff / 86400000);
      const hours = Math.floor((diff % 86400000) / 3600000);
      const minutes = Math.floor((diff % 3600000) / 60000);
      const seconds = Math.floor((diff % 60000) / 1000);
      if (fields.days) fields.days.textContent = String(days).padStart(2, "0");
      if (fields.hours) fields.hours.textContent = String(hours).padStart(2, "0");
      if (fields.minutes) fields.minutes.textContent = String(minutes).padStart(2, "0");
      if (fields.seconds) fields.seconds.textContent = String(seconds).padStart(2, "0");
      if (diff <= 0) clearInterval(timer);
    };
    tick();
    const timer = setInterval(tick, 1000);
  });

  /* ---------------------------------------------------------------------
     Account: new address panel, copy buttons, confirmations
     --------------------------------------------------------------------- */
  document.querySelectorAll("[data-new-address]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const panel = document.getElementById("new-address-panel");
      if (!panel) return;
      panel.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", panel.classList.contains("is-open") ? "true" : "false");
      if (panel.classList.contains("is-open")) {
        panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
        const first = panel.querySelector("input, select, textarea");
        if (first) setTimeout(() => first.focus(), 180);
      }
    });
  });

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const value = btn.dataset.copy;
      try {
        await navigator.clipboard.writeText(value);
        toast("Copied to clipboard.", "success", 1800);
      } catch (e) {
        toast("Copy failed — please copy manually.", "warning");
      }
    });
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm || "Are you sure?")) event.preventDefault();
    });
  });

  /* ---------------------------------------------------------------------
     Back to top
     --------------------------------------------------------------------- */
  const backToTop = document.getElementById("back-to-top");
  if (backToTop) {
    const toggleBackTop = () => backToTop.classList.toggle("is-visible", window.scrollY > 500);
    toggleBackTop();
    window.addEventListener("scroll", toggleBackTop, { passive: true });
    backToTop.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));
  }

  /* ---------------------------------------------------------------------
     Submit-once guard: disable the button after the first submit so a
     double click cannot create the same record twice.
     --------------------------------------------------------------------- */
  document.querySelectorAll("form[data-submit-once]").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type='submit']");
      if (!button || button.disabled) return;
      window.setTimeout(() => {
        button.disabled = true;
        button.setAttribute("aria-busy", "true");
      }, 0);
    });
  });

  /* ---------------------------------------------------------------------
     Reveal sections on scroll (progressive enhancement)
     --------------------------------------------------------------------- */
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -60px 0px" }
    );
    document.querySelectorAll("[data-reveal]").forEach((el) => observer.observe(el));
  }
})();
