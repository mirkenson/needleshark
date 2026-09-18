// Integration contract tests for the real Apps Script source, with in-memory Google services.
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');
const assert = require('node:assert/strict');
function fixture() {
  const headers=['ID заявки','Дата UTC','Имя','Телефон / email','Задача','Файл в письме','Статус заявки','Уведомление'];
  const rows=[headers.slice()], links=new Map(), files=new Map(), mails=[];
  let serial=0, privateFolder=true, failAppend=false, failMail=false;
  const props={SHARED_SECRET:'test-secret-'.repeat(4)};
  const sheet={
    getLastRow:()=>rows.length,
    getParent:()=>({getUrl:()=> 'https://docs.google.com/test-only'}),
    appendRow:row=>{if(failAppend)throw Error('sheet unavailable');rows.push(row)},
    getRange:(r,c,h=1,w=1)=>({
      getValues:()=>[Array.from({length:w},(_,i)=>rows[r-1]?.[c+i-1]||'')],
      setValues:values=>{values[0].forEach((v,i)=>{rows[r-1][c+i-1]=v});},
      getValue:()=>rows[r-1][c-1], setValue:v=>{rows[r-1][c-1]=v},
      setRichTextValue:v=>{rows[r-1][c-1]=v.text;links.set(r,v.url)},
      createTextFinder:id=>({matchEntireCell:()=>({findNext:()=>{const i=rows.findIndex(row=>row[0]===id);return i>0?{getRow:()=>i+1}:null}})})
    })
  };
  const blob=(bytes,type,name)=>({bytes,type,name,copyBlob(){return blob(this.bytes,this.type,this.name)},setName(n){this.name=n;return this}});
  const folder={getId:()=> 'test-folder-12345',isTrashed:()=>false,getSharingAccess:()=>privateFolder?'PRIVATE':'ANYONE',
    getFilesByName:name=>({hasNext:()=>files.has(name),next:()=>files.get(name)}),
    createFile:b=>{const id='test-file-'+(++serial)+'123456789';const f={getId:()=>id,isTrashed:()=>false,getSharingAccess:()=> 'PRIVATE'};files.set(b.name,f);return f}
  };
  const sandbox={
    SpreadsheetApp:{openById:()=>({getSheetByName:()=>sheet}),flush(){},newRichTextValue:()=>({text:'',url:'',setText(t){this.text=t;return this},setLinkUrl(u){this.url=u;return this},build(){return {text:this.text,url:this.url}}})},
    DriveApp:{Access:{PRIVATE:'PRIVATE'},createFolder:()=>folder,getFolderById:()=>folder},
    PropertiesService:{getScriptProperties:()=>({getProperty:k=>props[k],setProperty:(k,v)=>{props[k]=v}})},
    LockService:{getScriptLock:()=>({waitLock(){},hasLock:()=>true,releaseLock(){}})},
    MailApp:{getRemainingDailyQuota:()=>100,sendEmail:m=>{if(failMail)throw Error('mail unavailable');mails.push(m)}},
    ContentService:{MimeType:{JSON:'application/json'},createTextOutput:t=>({setMimeType:()=>JSON.parse(t)})},
    Utilities:{base64Decode:s=>[...Buffer.from(s,'base64')],newBlob:blob}
  };
  runInNewContext(readFileSync(__dirname+'/Code.gs','utf8'),sandbox);
  const lead={id:'12345678-1234-4234-8234-123456789abc',name:'ТЕСТ',contact:'test@example.com',question:'Проверка',created_at:'2026-09-18T00:00:00Z',business_company:'=TEST',business_intent:'custom',attachment:{name:'ТЕСТ.pdf',type:'application/pdf',data:Buffer.from('%PDF-test').toString('base64')}};
  return {lead,rows,links,files,mails,props,sandbox,setPrivate:v=>privateFolder=v,setFailAppend:v=>failAppend=v,setFailMail:v=>failMail=v,
    post:(l=lead,token=props.SHARED_SECRET)=>sandbox.doPost({postData:{contents:JSON.stringify({token,lead:l})}})};
}
const tests={
  'B2B fields, rich-text file link, attachment and mail':()=>{const f=fixture(),r=f.post();assert.equal(r.ok,true);assert.equal(f.rows[1][8],"'=TEST");assert.equal(f.rows[1][9],'Изделие на заказ');assert.equal(f.links.get(2),r.attachment_url);assert.equal(f.mails.length,1);assert.ok(f.mails[0].body.includes(r.attachment_url));assert.equal(f.mails[0].attachments[0].name,'ТЕСТ.pdf')},
  'retry reuses row, file, and sent mail':()=>{const f=fixture(),a=f.post(),b=f.post();assert.equal(a.attachment_url,b.attachment_url);assert.equal(f.files.size,1);assert.equal(f.rows.length,2);assert.equal(f.mails.length,1)},
  'failure after Drive write does not duplicate file':()=>{const f=fixture();f.setFailAppend(true);assert.equal(f.post().ok,false);assert.equal(f.files.size,1);f.setFailAppend(false);assert.equal(f.post().ok,true);assert.equal(f.files.size,1)},
  'mail failure keeps one row and file until retry':()=>{const f=fixture();f.setFailMail(true);assert.equal(f.post().ok,false);assert.equal(f.rows[1][7],'Ожидает отправки');f.setFailMail(false);assert.equal(f.post().ok,true);assert.equal(f.files.size,1);assert.equal(f.rows.length,2)},
  'public folder fails closed':()=>{const f=fixture();f.setPrivate(false);assert.equal(f.post().ok,false);assert.equal(f.files.size,0);assert.equal(f.rows.length,1)},
  'legacy request without file':()=>{const f=fixture();const l={...f.lead};delete l.attachment;delete l.business_company;delete l.business_intent;const r=f.post(l);assert.equal(r.ok,true);assert.equal(r.attachment_url,null);assert.equal(f.files.size,0);assert.equal(f.rows[1][8],'')},
  'bad secret, direction or file rejected':()=>{const f=fixture();assert.equal(f.post(f.lead,'bad').ok,false);assert.equal(f.post({...f.lead,business_intent:'toString'}).ok,false);assert.equal(f.post({...f.lead,attachment:{...f.lead.attachment,type:'text/html'}}).ok,false);assert.equal(f.rows.length,1)},
  'conflicting new column headers do not overwrite data':()=>{const f=fixture();f.rows[0][8]='Чужая колонка';assert.equal(f.post().ok,false);assert.equal(f.rows[0][8],'Чужая колонка')},
  'file label is literal rich text, never a formula':()=>{const f=fixture();f.lead.attachment.name='=IMPORTDATA.pdf';assert.equal(f.post().ok,true);assert.equal(f.rows[1][5],'=IMPORTDATA.pdf');assert.ok(f.links.get(2))}
};
for(const [name,test] of Object.entries(tests)){test();console.log('PASS '+name)}
console.log(Object.keys(tests).length+' Apps Script contract tests passed');
