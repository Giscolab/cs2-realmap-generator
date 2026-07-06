/*
 * ui-chrome.js — chrome éditeur (design Figma RedesignForErgonomics).
 * Couche purement visuelle et additive :
 *  - les boutons [data-proxy] relaient le clic vers les contrôles existants
 *    (aucune logique métier dupliquée, les handlers d'origine restent seuls maîtres) ;
 *  - les onglets [data-tab-target] montrent/masquent des sections déjà présentes ;
 *  - les menus <details class="menu"> se ferment mutuellement et au clic extérieur.
 * Ce fichier ne modifie aucun autre script et peut être retiré sans casser l'app.
 */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  function bindProxies() {
    var proxies = document.querySelectorAll("[data-proxy]");
    Array.prototype.forEach.call(proxies, function (proxy) {
      proxy.addEventListener("click", function () {
        var target = document.getElementById(proxy.getAttribute("data-proxy"));
        if (target && target !== proxy) {
          target.click();
        }
        var menu = proxy.closest("details.menu");
        if (menu) {
          menu.removeAttribute("open");
        }
      });
    });
  }

  function bindMenus() {
    var menus = document.querySelectorAll("details.menu");

    Array.prototype.forEach.call(menus, function (menu) {
      menu.addEventListener("toggle", function () {
        if (!menu.open) {
          return;
        }
        Array.prototype.forEach.call(menus, function (other) {
          if (other !== menu) {
            other.removeAttribute("open");
          }
        });
      });
    });

    document.addEventListener("click", function (event) {
      Array.prototype.forEach.call(menus, function (menu) {
        if (menu.open && !menu.contains(event.target)) {
          menu.removeAttribute("open");
        }
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        Array.prototype.forEach.call(menus, function (menu) {
          menu.removeAttribute("open");
        });
      }
    });
  }

  function bindTabList(list) {
    var tabs = list.querySelectorAll("[data-tab-target]");

    Array.prototype.forEach.call(tabs, function (tab) {
      tab.addEventListener("click", function () {
        Array.prototype.forEach.call(tabs, function (other) {
          var active = other === tab;
          var panel = document.getElementById(other.getAttribute("data-tab-target"));

          other.classList.toggle("is-active", active);
          other.setAttribute("aria-selected", active ? "true" : "false");
          if (panel) {
            panel.hidden = !active;
          }
        });
      });
    });
  }

  function bindTabs() {
    var lists = document.querySelectorAll(".tab-list, .analysis-tabs");
    Array.prototype.forEach.call(lists, bindTabList);
  }

  ready(function () {
    bindProxies();
    bindMenus();
    bindTabs();
  });
})();
