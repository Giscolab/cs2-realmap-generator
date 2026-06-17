(function (App) {
  "use strict";

  function byId(id) {
    return document.getElementById(id);
  }

  function setText(element, value) {
    if (element) {
      element.textContent = value;
    }
  }

  function fallbackCopy(text) {
    var field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "readonly");
    field.style.position = "fixed";
    field.style.left = "-9999px";
    document.body.appendChild(field);
    field.select();
    document.execCommand("copy");
    field.remove();
  }

  function copyText(text, onDone) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(onDone).catch(function () {
        fallbackCopy(text);
        onDone();
      });
      return;
    }

    fallbackCopy(text);
    onDone();
  }

  function flashButton(button, label) {
    if (!button) {
      return;
    }
    var original = button.textContent;
    button.textContent = label;
    window.setTimeout(function () {
      button.textContent = original;
    }, 1100);
  }

  App.CS2HelperUi = {
    byId: byId,
    setText: setText,
    copyText: copyText,
    flashButton: flashButton
  };
})(window.CS2Zoning = window.CS2Zoning || {});
