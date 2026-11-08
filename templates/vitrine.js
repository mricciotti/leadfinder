
(() => {
  document.documentElement.classList.add("js");
  const seen = "IntersectionObserver" in window ? new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        seen.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 }) : null;
  document.querySelectorAll(".reveal").forEach((item) => (seen ? seen.observe(item) : item.classList.add("in")));

  const toggle = document.querySelector("[data-menu-button]");
  const menu = document.querySelector("[data-menu]");
  if (toggle && menu) {
    toggle.addEventListener("click", () => {
      const open = menu.hidden;
      menu.hidden = !open;
      toggle.setAttribute("aria-expanded", String(open));
    });
    menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => {
      menu.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    }));
  }

  const builder = document.querySelector("[data-builder]");
  if (builder) {
    const phone = builder.dataset.phone || "";
    const leadIn = builder.dataset.leadIn || "Olá!";
    const send = builder.querySelector("[data-send]");
    const preview = builder.querySelector("[data-preview]");
    const nameInput = builder.querySelector("[data-client]");
    const picks = [...builder.querySelectorAll("[data-pick]")];
    let service = "";
    const update = () => {
      const who = nameInput.value.trim().slice(0, 40);
      const text = leadIn + (service ? ": " + service : "") + "." + (who ? " Meu nome é " + who + "." : "");
      preview.textContent = text;
      send.href = /^\d{12,13}$/.test(phone) ? "https://wa.me/" + phone + "?text=" + encodeURIComponent(text) : "#";
    };
    const choose = (name) => {
      service = name;
      picks.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.pick === name)));
      update();
    };
    picks.forEach((button) => button.addEventListener("click", () => choose(button.dataset.pick)));
    document.querySelectorAll("[data-service-link]").forEach((link) => link.addEventListener("click", () => choose(link.dataset.serviceLink)));
    nameInput.addEventListener("input", update);
    update();
  }
})();
