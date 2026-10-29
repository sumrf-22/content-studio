const http = require('http');

const get = (url) => new Promise((resolve, reject) => {
  http.get(url, (r) => {
    let b = '';
    r.on('data', (c) => { b += c; });
    r.on('end', () => resolve(b));
  }).on('error', reject);
});

get('http://127.0.0.1:8080/api/state')
  .then((b) => {
    const d = JSON.parse(b);
    const items = d.items || [];
    console.log('total items:', items.length);
    console.log('pending_approval:', items.filter((i) => i.status === 'pending_approval').length);
    if (items.length) {
      console.log('sample item[0]:', JSON.stringify(items[0]).slice(0, 250));
    }
    console.log('activity count:', d.activity ? d.activity.length : 0);
  })
  .catch((e) => console.log('error:', e));
