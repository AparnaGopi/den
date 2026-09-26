document.querySelectorAll('input[type=file]').forEach(input => {
  input.accept = 'image/jpeg,image/png,image/webp';
  const previews = document.createElement('div'); previews.className = 'upload-previews'; input.after(previews);
  let urls = [];
  function render() {
    urls.forEach(URL.revokeObjectURL); urls = []; previews.replaceChildren(); input.setCustomValidity('');
    Array.from(input.files).forEach((file, index) => {
      if (file.size > 5 * 1024 * 1024 || !['image/jpeg','image/png','image/webp'].includes(file.type)) input.setCustomValidity('Use JPEG, PNG or WebP images up to 5 MB each.');
      const figure = document.createElement('figure'); const img = document.createElement('img');
      img.src = URL.createObjectURL(file); urls.push(img.src); img.alt = file.name;
      const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remove ' + file.name;
      remove.onclick = () => { const files = new DataTransfer(); Array.from(input.files).forEach((item, i) => { if (i !== index) files.items.add(item); }); input.files = files.files; render(); };
      figure.append(img, remove); previews.append(figure);
    });
  }
  input.addEventListener('change', render);
});
const create = document.getElementById('create-description');
if (create) create.addEventListener('click', async () => {
  const status = document.getElementById('description-status'); create.disabled = true;
  try {
    const data = new FormData(document.getElementById('vendor-editor'));
    // Description generation never uploads or saves images.
    for (const key of Array.from(data.keys())) if (data.get(key) instanceof File) data.delete(key);
    const response = await fetch(create.dataset.url, {method:'POST', body:data});
    const result = await response.json();
    if (!response.ok) throw new Error(Object.entries(result.errors || {}).map(([key, value]) => key + ': ' + value.join(' ')).join(' '));
    document.getElementById('id_description').value = result.description;
    status.textContent = 'Draft created. Edit the description, then save your profile.';
  } catch (error) { status.textContent = error.message || 'Unable to create description. Please try again.'; }
  finally { create.disabled = false; }
});
