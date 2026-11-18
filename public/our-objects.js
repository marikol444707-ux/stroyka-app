(function () {
  var cards = Array.prototype.slice.call(document.querySelectorAll(".object-card"));
  var dialog = document.getElementById("object-lightbox");
  var image = document.getElementById("object-lightbox-image");
  var caption = document.getElementById("object-lightbox-caption");
  var count = document.getElementById("object-lightbox-count");
  var closeButton = document.getElementById("object-lightbox-close");
  var prevButton = document.getElementById("object-lightbox-prev");
  var nextButton = document.getElementById("object-lightbox-next");
  if (!cards.length || !dialog || !image || !caption || !count || !closeButton || !prevButton || !nextButton) return;
  if (typeof dialog.showModal !== "function") return;

  var index = 0;
  var opener = null;

  function show(nextIndex) {
    index = (nextIndex + cards.length) % cards.length;
    var card = cards[index];
    var text = card.getAttribute("data-caption") || "";
    image.src = card.getAttribute("href");
    image.alt = text;
    caption.textContent = text;
    count.textContent = (index + 1) + " из " + cards.length;
  }

  function openAt(nextIndex, source) {
    opener = source;
    show(nextIndex);
    if (!dialog.open) dialog.showModal();
    closeButton.focus();
  }

  function close() {
    if (dialog.open) dialog.close();
  }

  cards.forEach(function (card, cardIndex) {
    card.addEventListener("click", function (event) {
      if (event.defaultPrevented) return;
      if (event.button !== 0) return;
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      openAt(cardIndex, card);
    });
  });

  closeButton.addEventListener("click", close);
  prevButton.addEventListener("click", function () { show(index - 1); });
  nextButton.addEventListener("click", function () { show(index + 1); });

  dialog.addEventListener("click", function (event) {
    var panel = dialog.querySelector(".lightbox-panel");
    if (panel && !panel.contains(event.target)) close();
  });

  dialog.addEventListener("close", function () {
    image.removeAttribute("src");
    image.alt = "";
    if (opener && typeof opener.focus === "function") opener.focus();
  });

  dialog.addEventListener("keydown", function (event) {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      show(index - 1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      show(index + 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      show(0);
    } else if (event.key === "End") {
      event.preventDefault();
      show(cards.length - 1);
    }
  });
})();
