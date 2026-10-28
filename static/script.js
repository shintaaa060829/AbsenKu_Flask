document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll("[data-open]").forEach(function (button) {
    button.addEventListener("click", function () {
      const dialog = document.getElementById(button.dataset.open);
      if (dialog && typeof dialog.showModal === "function") dialog.showModal();
    });
  });

  document.querySelectorAll("[data-close]").forEach(function (button) {
    button.addEventListener("click", function () {
      const dialog = document.getElementById(button.dataset.close);
      if (dialog) dialog.close();
    });
  });

  document.querySelectorAll("dialog").forEach(function (dialog) {
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
  });

  document.querySelectorAll(".alert").forEach(function (box) {
    setTimeout(function () {
      box.style.transition = "opacity .35s";
      box.style.opacity = "0";
      setTimeout(function () { box.remove(); }, 400);
    }, 4500);
  });
});
