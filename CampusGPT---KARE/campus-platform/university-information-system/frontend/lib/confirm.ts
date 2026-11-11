/** Two-step confirmation. The second step requires the exact phrase. */
export function confirmPhrase(options: { title: string; detail: string; phrase: string }): Promise<boolean> {
  const phrase = options.phrase.trim();
  return new Promise((resolve) => {
    const root = document.createElement("div");
    root.className = "fixed inset-0 z-[80] flex items-center justify-center bg-slate-900/50 p-4";
    const box = document.createElement("div");
    box.className = "w-full max-w-md rounded-xl bg-white p-5 shadow-xl";
    root.appendChild(box);
    document.body.appendChild(root);

    const close = (answer: boolean) => {
      root.remove();
      resolve(answer);
    };

    const showStep = (step: 1 | 2) => {
      box.replaceChildren();
      const title = document.createElement("h2");
      title.className = "text-lg font-bold text-[#0B2A4A]";
      title.textContent = step === 1 ? options.title : "Second confirmation";
      const detail = document.createElement("p");
      detail.className = "mt-2 text-sm text-slate-600 whitespace-pre-wrap";
      detail.textContent =
        step === 1
          ? options.detail
          : `This writes to the database and cannot be undone. Type ${phrase} to continue.`;
      box.append(title, detail);
      let input: HTMLInputElement | null = null;
      if (step === 2) {
        input = document.createElement("input");
        input.className = "mt-3 w-full rounded-lg border px-3 py-2 text-sm";
        input.placeholder = phrase;
        input.autocomplete = "off";
        box.appendChild(input);
      }
      const actions = document.createElement("div");
      actions.className = "mt-4 flex justify-end gap-2";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "px-3 py-2 rounded-lg border text-sm";
      cancel.textContent = "Cancel";
      cancel.onclick = () => close(false);
      const next = document.createElement("button");
      next.type = "button";
      next.className = "px-3 py-2 rounded-lg bg-[#0B2A4A] text-white text-sm";
      next.textContent = step === 1 ? "Continue" : "Confirm";
      next.onclick = () => {
        if (step === 1) {
          showStep(2);
          return;
        }
        if ((input?.value || "").trim().toLowerCase() !== phrase.toLowerCase()) {
          detail.textContent = `That does not match. Type ${phrase} exactly.`;
          return;
        }
        close(true);
      };
      actions.append(cancel, next);
      box.appendChild(actions);
      input?.focus();
    };

    showStep(1);
  });
}
