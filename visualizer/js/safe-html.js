(function (App) {
  "use strict";

  function safeText(value, fallback) {
    if (value === null || value === undefined) {
      return fallback || "";
    }
    var text = String(value).trim();
    return text || (fallback || "");
  }

  function escapeHTML(value) {
    return safeText(value).replace(/[&<>"']/g, function (char) {
      return {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char];
    });
  }

  function escapeAttribute(value) {
    return escapeHTML(value).replace(/`/g, "&#96;");
  }

  App.SafeHTML = {
    safeText: safeText,
    escapeHTML: escapeHTML,
    escapeAttribute: escapeAttribute
  };
})(window.CS2Zoning = window.CS2Zoning || {});
