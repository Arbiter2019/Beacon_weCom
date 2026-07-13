import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../message-archive-prototype.html', import.meta.url), 'utf8');
const messageListBlock = html.match(/<div class="message-list" id="messageList">[\s\S]*?<\/div>\s*<\/section>/)?.[0] ?? '';

const assertions = [
  {
    name: 'bottom composer container is removed',
    pass: !/class="composer"/.test(html) && !/\.composer\s*\{/.test(html),
  },
  {
    name: 'hidden message count remains available for script updates',
    pass: /id="messageCount"[^>]*hidden[^>]*aria-hidden="true"/.test(messageListBlock),
  },
  {
    name: 'end marker lives inside the message list as disabled input placeholder',
    pass: /class="message-end-marker"[\s\S]*?<input[\s\S]*placeholder="到底了"[\s\S]*disabled/.test(messageListBlock),
  },
];

const failed = assertions.filter((assertion) => !assertion.pass);

if (failed.length) {
  console.error('Composer end marker check failed:');
  for (const failure of failed) console.error(`- ${failure.name}`);
  process.exit(1);
}

console.log(`Composer end marker check passed (${assertions.length}/${assertions.length}).`);
