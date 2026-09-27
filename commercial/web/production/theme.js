"use strict";
(function () {
  const themes = ["light", "dark", "green", "blue", "red"];
  let selected = "light";
  try { const saved = localStorage.getItem("avan-theme"); if (themes.includes(saved)) selected = saved; } catch (_) {}
  document.documentElement.dataset.theme = selected;
  document.addEventListener("DOMContentLoaded", function () {
    const picker = document.getElementById("theme-choice");
    if (!picker) return;
    picker.value = selected;
    picker.addEventListener("change", function () {
      if (!themes.includes(picker.value)) return;
      document.documentElement.dataset.theme = picker.value;
      try { localStorage.setItem("avan-theme", picker.value); } catch (_) {}
    });
  });
})();
