(() => {
  const form = document.getElementById('vendor-wizard');
  if (!form) return;
  const state = JSON.parse(document.getElementById('vendor-wizard-data').textContent);
  const status = document.getElementById('save-status');
  let timer, saving = Promise.resolve(), submitting = false, dirty = false, failed = false;
  const field = (name) => form.querySelector(`[name="${name}"]`);
  function conditionals(rebuild = false) {
    const type = field('vendor_type');
    if (type) {
      const other = field('other_enabled');
      if (type.value === 'OTHER') other.checked = true;
      form.querySelector('[data-field="other_services"]').hidden = !(other.checked || type.value === 'OTHER');
      if (rebuild) {
        const selected = new Set([...form.querySelectorAll('[name="specific_services"]:checked')].map((input) => input.value));
        const container = document.getElementById('id_specific_services');
        container.replaceChildren();
        state.service_catalogue.filter((item) => item.saved || item.types.includes(type.value)).forEach((item) => {
          const label = document.createElement('label'), checkbox = document.createElement('input');
          checkbox.type = 'checkbox'; checkbox.name = 'specific_services'; checkbox.value = item.value;
          checkbox.checked = selected.has(item.value);
          label.append(checkbox, document.createTextNode(item.label)); container.append(label);
        });
      }
    }
    const pricing = field('pricing_type');
    if (pricing) {
      form.querySelector('[data-field="price"]').hidden = pricing.value === 'CONTACT_FOR_QUOTE';
      const labels = { HOURLY: 'Price per hour (CAD)', PER_PERSON: 'Price per person (CAD)', PER_ITEM: 'Price per item (CAD)', STARTING_FROM: 'Starting price (CAD)', FIXED: 'Fixed price (CAD)' };
      form.querySelector('[data-field="price"] label').textContent = labels[pricing.value] || 'Price (CAD)';
    }
  }
  function preview(id, url, alt) {
    const node = document.getElementById(id);
    if (!node) return;
    node.replaceChildren();
    if (url) { const img = document.createElement('img'); img.src = url; img.alt = alt; img.className = 'wizard-image'; node.append(img); }
  }
  function autosave() {
    saving = saving.then(async () => {
      const body = new FormData(form);
      body.set('action', 'save');
      const uploads = [...form.querySelectorAll('input[type=file]')].filter((input) => input.files.length).map((input) => ({ input, file: input.files[0] }));
      body.set('revision', field('revision').value);
      status.textContent = 'Saving progress…';
      try {
        const response = await fetch(form.getAttribute('action') || window.location.href, { method: 'POST', body, headers: { Accept: 'application/json' } });
        const saved = await response.json();
        if (!response.ok) throw new Error(Object.values(saved.errors).flat().join(' '));
        field('revision').value = saved.revision;
        uploads.forEach(({ input, file }) => { if (input.files[0] === file) input.value = ''; });
        preview('logo-preview', saved.logo_url, 'Saved company logo');
        preview('cover-preview', saved.cover_url, 'Saved cover photo');
        const gallery = document.getElementById('portfolio-preview');
        if (gallery) { gallery.replaceChildren(); saved.photos.forEach((photo) => { const figure = document.createElement('figure'), img = document.createElement('img'), caption = document.createElement('figcaption'); img.className = 'wizard-image'; img.src = photo.url; img.alt = photo.caption || 'Portfolio photo'; caption.textContent = photo.caption; const remove = document.createElement('button'); remove.type = 'submit'; remove.name = 'action'; remove.value = 'remove_photo'; remove.dataset.photoId = photo.id; remove.className = 'button button-secondary'; remove.textContent = 'Remove photo'; figure.append(img, caption, remove); gallery.append(figure); }); }
        status.textContent = 'Progress saved. You can leave and return.'; failed = false;
      } catch (error) { status.textContent = `Progress could not be saved. ${error.message} Use Save progress to retry.`; failed = true; }
    });
    return saving;
  }
  function changed(event) {
    if (submitting) return;
    dirty = true;
    conditionals(event.target.name === 'vendor_type');
    clearTimeout(timer);
    timer = setTimeout(() => { dirty = false; void autosave(); }, 800);
  }
  form.addEventListener('input', changed);
  form.addEventListener('change', changed);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (submitting) return;
    submitting = true; clearTimeout(timer);
    const button = event.submitter;
    await saving;
    field('target').value = button?.dataset.target || '';
    field('photo_id').value = button?.dataset.photoId || '';
    const action = document.createElement('input'); action.type = 'hidden'; action.name = 'action'; action.value = button?.value || 'save'; form.append(action);
    form.submit();
  });
  window.addEventListener('beforeunload', (event) => { if (!submitting && (dirty || failed || status.textContent === 'Saving progress…')) { event.preventDefault(); event.returnValue = ''; } });
  conditionals();
})();

