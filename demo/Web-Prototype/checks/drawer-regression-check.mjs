import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../message-archive-prototype.html', import.meta.url), 'utf8');
const baseWorkspaceRule = html.match(/\.workspace\s*\{[\s\S]*?\}/)?.[0] ?? '';

const assertions = [
  {
    name: 'desktop workspace uses menu plus three content columns and does not reserve a detail column',
    pass: /grid-template-columns:\s*176px\s+260px\s+minmax\(280px,\s*360px\)\s+minmax\(420px,\s*1fr\);/.test(baseWorkspaceRule),
  },
  {
    name: 'desktop media query keeps menu plus three content columns',
    pass: /@media\s*\(max-width:\s*1180px\)\s*\{[\s\S]*?\.workspace\s*\{\s*grid-template-columns:\s*156px\s+236px\s+320px\s+minmax\(0,\s*1fr\);\s*\}/.test(html)
      && !/grid-template-columns:\s*156px\s+236px\s+320px\s+minmax\(0,\s*1fr\)\s+320px/.test(html),
  },
  {
    name: 'detail pane is fixed overlay drawer by default',
    pass: /\.detail-pane\s*\{[\s\S]*?position:\s*fixed;[\s\S]*?right:\s*var\(--space-4\);[\s\S]*?transform:\s*translateX\(calc\(100% \+ var\(--space-8\)\)\);/.test(html),
  },
  {
    name: 'open state slides drawer into view',
    pass: /\.detail-pane\.open\s*\{\s*transform:\s*translateX\(0\);\s*\}/.test(html),
  },
  {
    name: 'detail drawer keeps the single visible trigger and safe optional legacy binding',
    pass: html.includes('byId("openDetail").addEventListener("click", openDetail);')
      && html.includes('bindIfPresent("openDetailTop", "click", openDetail);')
      && /byId\("drawerBackdrop"\)\.addEventListener\("click",\s*\(\)\s*=>\s*\{[\s\S]*?closeDetail\(\);[\s\S]*?closeMessageSearch\(\);[\s\S]*?\}\);/.test(html)
      && !html.includes('id="openDetailTop"'),
  },
  {
    name: 'message search drawer is a fixed overlay opened from a separate icon trigger',
    pass: /id="openMessageSearch"[\s\S]*aria-controls="messageSearchPane"[\s\S]*aria-expanded="false"/.test(html)
      && /\.message-search-pane\s*\{[\s\S]*?position:\s*fixed;[\s\S]*?transform:\s*translateX\(calc\(100% \+ var\(--space-8\)\)\);/.test(html)
      && /function openMessageSearch\(\)[\s\S]*?byId\("messageSearchPane"\)\.classList\.add\("open"\)/.test(html),
  },
];

const failed = assertions.filter((assertion) => !assertion.pass);

if (failed.length) {
  console.error('Drawer regression check failed:');
  for (const failure of failed) console.error(`- ${failure.name}`);
  process.exit(1);
}

console.log(`Drawer regression check passed (${assertions.length}/${assertions.length}).`);
