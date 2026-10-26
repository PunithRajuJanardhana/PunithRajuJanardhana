"""Generate the profile's self-contained, GitHub-compatible SVG artwork."""
from pathlib import Path
from html import escape
ROOT = Path(__file__).resolve().parents[1] / 'assets'

def t(x,y,label,size=16,color='#f4f6ff',extra=''):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" {extra}>{escape(label)}</text>'

def save(name,h,body):
    ROOT.joinpath(name+'.svg').write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="{h}" viewBox="0 0 1080 {h}" role="img" aria-labelledby="title desc"><title id="title">{escape(name.replace('-', ' ').title())}</title><desc id="desc">Original profile artwork for Punith Raju Janardhana.</desc><defs><pattern id="grid" width="36" height="36" patternUnits="userSpaceOnUse"><path d="M36 0H0V36" fill="none" stroke="#283148" stroke-width=".6"/></pattern><linearGradient id="ink"><stop stop-color="#baff39"/><stop offset="1" stop-color="#53e5ff"/></linearGradient><radialGradient id="light"><stop stop-color="#576bff" stop-opacity=".32"/><stop offset="1" stop-color="#090b13" stop-opacity="0"/></radialGradient></defs><style>text{{font-family:Arial,Helvetica,sans-serif}}.mono{{font-family:monospace;letter-spacing:2px}}.orbit{{transform-origin:835px 200px;animation:spin 32s linear infinite}}.pulse{{animation:pulse 4s ease-in-out infinite}}@keyframes spin{{to{{transform:rotate(360deg)}}}}@keyframes pulse{{50%{{opacity:.35}}}}@media(prefers-reduced-motion:reduce){{.orbit,.pulse{{animation:none}}}}</style><rect width="1080" height="{h}" rx="20" fill="#090b13"/><rect width="1080" height="{h}" rx="20" fill="url(#grid)"/>{body}<rect x=".5" y=".5" width="1079" height="{h-1}" rx="20" fill="none" stroke="#32394e"/></svg>''')

b='<circle cx="810" cy="180" r="350" fill="url(#light)"/><path d="M690 0H1080V414H980Z" fill="#151834"/>'
b+=t(40,44,'PRJ® / PERSONAL FIELD NOTES',13,'#baff39','class="mono"')+t(1040,44,'VOL. 01 — ALWAYS IN PROGRESS',12,'#b7bfd4','text-anchor="end" class="mono"')
b+='<g class="orbit" fill="none" stroke="#7d8aff"><ellipse cx="835" cy="200" rx="179" ry="58" transform="rotate(-45 835 200)"/><ellipse cx="835" cy="200" rx="179" ry="58" transform="rotate(45 835 200)"/><circle cx="835" cy="200" r="134" stroke-dasharray="3 12"/><circle cx="961" cy="155" r="9" fill="#baff39" stroke="none"/></g>'
b+=t(33,161,'HEY, I’M',89,'#f4f6ff','font-weight="900" letter-spacing="-5"')+t(30,278,'PUNITH',134,'#baff39','font-weight="900" letter-spacing="-8"')+t(43,320,'RAJU JANARDHANA / SOFTWARE ENGINEER + PRODUCT BUILDER',15,'#bfc8df','class="mono"')
b+='<path d="M40 351H1040" stroke="#3b4358"/>'
b+=t(42,389,'BENGALURU ROOTS.',20,'#f4f6ff','font-weight="800"')+t(384,389,'SEATTLE CHAPTERS.',20,'#53e5ff','font-weight="800"')+t(730,389,'BUILDING WHAT’S NEXT.',20,'#baff39','font-weight="800"')
b+='<rect x="0" y="426" width="1080" height="57" fill="#baff39"/>'+t(540,461,'RELIABLE BACKENDS  /  USEFUL AI  /  PRODUCTS WITH A PURPOSE',17,'#090b13','text-anchor="middle" font-weight="800" letter-spacing="2"')
save('mission-control',483,b)

b=t(38,44,'01 / CURRENT FOCUS',13,'#baff39','class="mono"')+'<circle class="pulse" cx="1019" cy="39" r="7" fill="#baff39"/>'
b+=t(32,143,'ALKSEA',100,'#f4f6ff','font-weight="900" letter-spacing="-5"')+t(40,185,'Wallet compliance infrastructure.',26,'#53e5ff')+t(40,225,'Security. Auditability. Operational reliability.',18,'#bdc7dc')
b+='<path d="M40 258H1040" stroke="#343c51"/>'
for i,(label,sub) in enumerate([('PERMISSIONS','Who can do what?'),('AUDIT TRAILS','How did we get here?'),('RECOVERY','What happens next?')]):
    x=40+i*341
    b+=f'<rect x="{x}" y="286" width="318" height="96" rx="10" fill="#141b2b" stroke="#39435b"/>'+t(x+18,320,label,17,'#baff39','font-weight="800"')+t(x+18,352,sub,16,'#c5cde0')
b+=t(40,425,'ENGINEERING FOR THE MOMENTS WHEN SYSTEMS FAIL.',14,'#c5cde0','class="mono"')+t(1040,425,'alksea.com ↗',16,'#53e5ff','text-anchor="end"')
b+='<g transform="translate(862 102)" fill="none" stroke="#baff39" stroke-width="3"><path d="M0-37 49-19V13C49 43 0 65 0 65S-49 43-49 13V-19Z"/><path d="m-21 10 15 15 30-37"/></g>'
save('alksea',455,b)

for name,num,title,tag,lines,col in [
 ('rupione','02','RUPIONE','LENDING / INDIA',['Apply once. Let lenders compete.','Compare offers in one place.'],'#c9a6ff'),
 ('yen-maga','03','YEN MAGA','EVENTS / COMMUNITY',['Discover events worth showing up for.','Co-founding with my sister, Vatsala.'],'#ffab79')]:
    b=t(38,44,num+' / OTHER VENTURES',13,col,'class="mono"')+'<rect x="861" y="21" width="178" height="32" rx="16" fill="#222534"/>'+t(950,42,'CURRENTLY PAUSED',12,'#d4d8e5','text-anchor="middle"')
    b+=t(32,138,title,84,col,'font-weight="900" letter-spacing="-4"')+t(40,182,tag,14,'#d4d8e5','class="mono"')
    b+=t(40,235,lines[0],22)+t(40,269,lines[1],20,'#bfc8db')
    b+='<path d="M765 86 1015 278M807 86 1057 278M723 86 973 278" stroke="'+col+'" stroke-width="12" opacity=".17"/>'
    save(name,305,b)
b=t(40,43,'04 / LEARNING BY BUILDING',13,'#53e5ff','class="mono"')
for i in range(3):
    x=40+i*155
    b+=f'<rect x="{x}" y="77" width="134" height="87" rx="9" fill="#221c2d" stroke="#655174"/>'+t(x+67,111,f'YC / 0{i+1}',13,'#c6afd6','text-anchor="middle" class="mono"')+t(x+67,145,'REJECTED',16,'#ffb0b8','text-anchor="middle" font-weight="800"')
b+=t(549,112,'STILL CURIOUS.',33,'#f4f6ff','font-weight="900"')+t(549,154,'STILL BUILDING.',33,'#baff39','font-weight="900"')
b+=t(40,210,'Three Y Combinator rejections. More reasons to keep going.',20,'#c5cde0')
save('keep-building',245,b)
b=t(40,45,'THE LOOP',13,'#53e5ff','class="mono"')
for x,n,label in [(40,'01','UNDERSTAND'),(389,'02','SHIP'),(738,'03','LEARN')]:
    b+=t(x,116,n,65,'#38435b','font-weight="900"')+t(x+92,109,label,25,'#baff39','font-weight="900"')
b+=t(40,173,'Seek discomfort. Stay curious. Keep building.',27,'#f4f6ff','font-weight="700"')+t(40,213,'HAVE SOMETHING WORTH BUILDING? LET’S TALK. ↗',14,'#53e5ff','class="mono"')
save('end-transmission',246,b)
