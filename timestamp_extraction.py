<!doctype html>
<html>
<head>
  <title>Timestamp Extraction</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 1000px; margin: 30px auto; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 28px; }
    img { max-width: 100%; border: 1px solid #ddd; border-radius: 8px; }
    a.btn { padding: 6px 10px; border-radius: 6px; background:#f3f3f3; text-decoration: none; }
    ul { background:#fafafa; padding:12px 16px; border-radius: 8px; }
  </style>
</head>
<body>
  <h2>Extracted Timestamps</h2>
  <p><a href="{{ url_for('dashboard') }}">← Back</a></p>

  <ul>
    {% for t in timestamps %}
      <li>{{ t }}</li>
    {% endfor %}
  </ul>

  <p><a class="btn" href="{{ url_for('export_timestamps') }}">📥 Export as TXT</a></p>

  <h3>Debug Previews</h3>
  {% if previews %}
    {% for p in previews %}
      <div class="row">
        <div>
          <p><strong>Full frame</strong></p>
          <img src="{{ url_for('static', filename='crops/' + p.full) }}">
        </div>
        <div>
          <p><strong>Cropped area</strong></p>
          <img src="{{ url_for('static', filename='crops/' + p.crop) }}">
        </div>
      </div>
    {% endfor %}
  {% else %}
    <p>No previews available yet.</p>
  {% endif %}
</body>
</html>
