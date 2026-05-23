document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("episode-search");
  const cards = document.querySelectorAll(".episode-card");
  const countEl = document.getElementById("search-count");
  const total = cards.length;

  function updateCount(visible) {
    if (!input.value.trim()) {
      countEl.textContent = `${total} episode${total !== 1 ? "s" : ""}`;
    } else {
      countEl.textContent = `${visible} of ${total}`;
    }
  }

  function highlight(text, query) {
    if (!query) return text;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return text.replace(new RegExp(`(${escaped})`, "gi"), "<em>$1</em>");
  }

  function filter() {
    const q = input.value.trim().toLowerCase();
    let visible = 0;

    cards.forEach(card => {
      const title = card.dataset.title || "";
      const overview = card.dataset.overview || "";

      const match = !q || title.includes(q) || overview.includes(q);

      if (match) {
        card.classList.remove("hidden");
        visible++;

        // Highlight matches
        const titleEl = card.querySelector(".ep-title");
        const overviewEl = card.querySelector(".ep-overview");
        const rawTitle = card.dataset.title;
        const rawOverview = card.dataset.overview;

        if (q) {
          titleEl.innerHTML = highlight(
            titleEl.textContent, input.value.trim()
          );
          if (overviewEl) {
            overviewEl.innerHTML = highlight(
              overviewEl.textContent, input.value.trim()
            );
            overviewEl.classList.add("highlighted");
          }
        } else {
          // Reset highlights
          titleEl.textContent = titleEl.textContent;
          if (overviewEl) {
            overviewEl.textContent = overviewEl.textContent;
            overviewEl.classList.remove("highlighted");
          }
        }
      } else {
        card.classList.add("hidden");
      }
    });

    updateCount(visible);
  }

  // Reset text content on clear so highlights don't accumulate
  function resetText() {
    cards.forEach(card => {
      const titleEl = card.querySelector(".ep-title");
      const overviewEl = card.querySelector(".ep-overview");
      const rawTitle = card.dataset.title;
      const rawOverview = card.dataset.overview;

      // Capitalise first letter to restore display casing (data-* is lowercased)
      // We keep originals in a separate data attr for safe restore
      if (card.dataset.titleOrig) titleEl.textContent = card.dataset.titleOrig;
      if (overviewEl && card.dataset.overviewOrig)
        overviewEl.textContent = card.dataset.overviewOrig;
    });
  }

  // Stash original (properly cased) text before any filtering
  cards.forEach(card => {
    const titleEl = card.querySelector(".ep-title");
    const overviewEl = card.querySelector(".ep-overview");
    card.dataset.titleOrig = titleEl ? titleEl.textContent : "";
    card.dataset.overviewOrig = overviewEl ? overviewEl.textContent : "";
    // Lowercase versions for matching
    card.dataset.title = card.dataset.titleOrig.toLowerCase();
    card.dataset.overview = card.dataset.overviewOrig.toLowerCase();
  });

  input.addEventListener("input", () => {
    resetText();
    filter();
  });

  // Initial count
  updateCount(total);
});
