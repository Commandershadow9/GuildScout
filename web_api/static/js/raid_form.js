document.addEventListener("DOMContentLoaded", () => {
  const templateCards = document.querySelectorAll("[data-template]");
  const tankInput = document.querySelector("input[name='tanks']");
  const healerInput = document.querySelector("input[name='healers']");
  const dpsInput = document.querySelector("input[name='dps']");
  const benchInput = document.querySelector("input[name='bench']");

  if (!templateCards.length) {
    return;
  }

  const applyTemplate = (card) => {
    if (!card) {
      return;
    }
    templateCards.forEach((item) => item.classList.remove("active"));
    card.classList.add("active");
    if (tankInput) tankInput.value = card.dataset.tanks || 0;
    if (healerInput) healerInput.value = card.dataset.healers || 0;
    if (dpsInput) dpsInput.value = card.dataset.dps || 0;
    if (benchInput) benchInput.value = card.dataset.bench || 0;
  };

  templateCards.forEach((card) => {
    card.addEventListener("click", () => applyTemplate(card));
  });

  const active = document.querySelector(".template-card.active");
  if (active) {
    applyTemplate(active);
  }
});
