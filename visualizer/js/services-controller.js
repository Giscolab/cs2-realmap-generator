(function (App) {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  function formatCount(value) {
    return Number(value || 0).toLocaleString("fr-FR");
  }

  function familyCard(family) {
    var implemented = Boolean(family.implemented);
    var card = el("article", "service-card");
    if (!implemented) {
      card.classList.add("is-disabled");
    }

    var head = el("div", "service-head");
    head.append(el("span", "service-name", family.label || family.key));

    var badge = el(
      "span",
      "service-badge " + (implemented ? "is-on" : "is-off"),
      implemented ? "connecté" : "non connecté"
    );
    head.append(badge);
    head.append(el("span", "service-count", formatCount(family.count)));
    card.append(head);

    var subs = el("div", "service-subs");
    (family.subcategories || []).forEach(function (sub) {
      var row = el("div", "service-sub");
      row.append(el("span", "service-sub-label", sub.label || sub.key));
      row.append(el("span", "service-sub-count", formatCount(sub.count)));
      subs.append(row);
    });
    card.append(subs);

    return card;
  }

  function render(servicesIndex) {
    var list = byId("services-list");
    var context = byId("services-context");
    if (!list) {
      return;
    }

    if (!servicesIndex || !Array.isArray(servicesIndex.families)) {
      if (context) {
        context.textContent = "Aucun index — régénérez le bundle";
      }
      list.replaceChildren(
        el("p", "services-empty", "Index des services indisponible pour ce bundle.")
      );
      return;
    }

    var families = servicesIndex.families;
    if (context) {
      context.textContent = families.length + " familles";
    }
    list.replaceChildren.apply(list, families.map(familyCard));
  }

  App.ServicesController = {
    create: function (options) {
      var servicesIndex = options && options.servicesIndex;
      return {
        render: function () {
          render(servicesIndex);
        }
      };
    }
  };
})(window.CS2Zoning = window.CS2Zoning || {});
