/** Room estimates include the full transcript. They are not tokenizer counts. */
export type ContextPolicy = {limit:number; systemReserve:number; sourceReserve:number; replyReserve:number; roomBudget:number; estimated:boolean};
export function estimateTextTokens(text:string):number {return Math.ceil(new TextEncoder().encode(text).length/3);}
export function roomTokens(messages:{content:string;failed?:boolean}[]):number {
  return messages.filter(m=>!m.failed && m.content.trim()).reduce((sum,m)=>sum+estimateTextTokens(m.content)+8,0);
}
export function roomContext(messages:{content:string;failed?:boolean}[],policy:ContextPolicy,input="") {
  const used=roomTokens(messages), pending=input.trim()?estimateTextTokens(input.trim())+8:0;
  const remaining=Math.max(0,policy.roomBudget-used);
  return {used,remaining,exhausted:used+pending>=policy.roomBudget,percent:Math.min(100,Math.round(used/Math.max(1,policy.roomBudget)*100))};
}
/** Rule confidence is a category, not an uncalibrated probability. */
export type TitleSuggestion = {title:string; confidence:"high"|"fallback"; provisional:boolean};
function cleanTitleText(text:string):string {
  return text.replace(/<\/?[a-z][^>]*>/gi," ").replace(/https?:\/\/\S+/gi," ")
    .replace(/\s+/g," ").trim();
}
function shortenTitle(text:string):string {
  const value=text.replace(/[?!.,:;]+$/g,"").trim();
  const words=value.split(/\s+/);let result="";
  for(const word of words.slice(0,9)){
    const next=(result+" "+word).trim();if(next.length>64)break;result=next;
  }
  if(!result)result="Percakapan";
  return result.charAt(0).toLocaleUpperCase("id-ID")+result.slice(1);
}
export function analyzeChatTitle(question:string):TitleSuggestion {
  const original=cleanTitleText(question);
  const normalized=original.toLocaleLowerCase("id-ID").replace(/[’']/g,"")
    .replace(/[^\p{L}\p{N}]+/gu," ").trim();
  if(!normalized)return {title:original?shortenTitle(original):"Percakapan umum",confidence:"fallback",provisional:true};
  const greeting=/^(?:(?:halo+|hallo+|hai+|hi|hello|helo|selamat pagi|selamat siang|selamat sore|selamat malam|assalamualaikum|salam|apa kabar|jst)(?:\s+|$))+$/i;
  if(greeting.test(normalized))return {title:"Sapaan awal",confidence:"high",provisional:true};
  if(/^(?:tes+t?|testing|ping|cek koneksi|uji coba|coba tes|tes chat)(?:\s+\d+)?$/i.test(normalized) || /^\d+$/.test(normalized))
    return {title:"Uji percakapan",confidence:"high",provisional:true};
  if(/^(?:makasih|terima kasih|thanks|thank you|oke|ok|sip|baik|siap|iya|ya)[\s!.,]*$/i.test(normalized))
    return {title:"Percakapan singkat",confidence:"high",provisional:true};

  const topics:[RegExp,string][]=[
    [/\bpbb(?: p2)?\b|\bpajak bumi (?:dan )?bangunan\b/i,"PBB"],
    [/\bbphtb\b|\bbea perolehan hak\b/i,"BPHTB"],
    [/\bpbjt\b|\bpajak barang dan jasa tertentu\b/i,"PBJT"],
    [/\bpajak (?:air tanah|airtanah)\b|\bpat\b/i,"Pajak Air Tanah"],
    [/\bpajak reklame\b|\breklame\b/i,"Pajak Reklame"],
  ];
  const found=topics.filter(([pattern])=>pattern.test(normalized)).map(([,name])=>name);
  // Ambiguous scope, negated intent, and several unrelated topics retain the user's wording.
  const ambiguous=/\b(perserikatan bangsa|united nations|bukan|jangan|selain|tanpa|tidak)\b/i.test(normalized);
  if(!ambiguous && found.length>1 && /\b(beda|bedanya|perbedaan|bandingkan|perbandingan|dibanding|vs|versus)\b/.test(normalized))
    return {title:shortenTitle("Perbandingan "+found.join(" dan ")),confidence:"high",provisional:false};
  if(!ambiguous && found.length===1){
    const topic=found[0];
    const intents:[RegExp,string][]=[
      [/\b(denda|sanksi)\b.*\b(telat|terlambat|keterlambatan)\b|\b(telat|terlambat|keterlambatan)\b.*\b(denda|sanksi)\b/,"Denda Keterlambatan"],
      [/\b(denda|sanksi)\b/,"Denda"],
      [/\b(hitung|hitungkan|itung|itungin|ngitung|perhitungan|simulasi)\b/,"Perhitungan"],
      [/\b(tunggakan|nunggak|menunggak)\b/,"Tunggakan"],
      [/\b(dasar hukum|pasal|landasan hukum)\b/,"Dasar Hukum"],
      [/\b(bebas|pembebasan)\b/,"Pembebasan"],
      [/\b(keringanan|pengurangan|diskon)\b/,"Keringanan"],
      [/\b(status|lunas|pelunasan)\b/,"Status Pembayaran"],
      [/\b(bayar|pembayaran|membayar)\b/,"Pembayaran"],
      [/\b(tarif|tarip|persen|persentase)\b/,"Tarif"],
      [/\b(daftar|pendaftaran|mendaftar)\b/,"Pendaftaran"],
    ];
    const intent=intents.find(([pattern])=>pattern.test(normalized))?.[1];
    return {title:intent?`${intent} ${topic}`:topic,confidence:"high",provisional:false};
  }
  // Unknown meaning keeps the user's wording, including the request verb.
  return {title:shortenTitle(original),confidence:"fallback",provisional:false};
}
export function suggestChatTitle(questions:string[]):string {
  let provisional:TitleSuggestion|undefined;
  for(const question of questions){
    if(!question.trim())continue;
    const suggestion=analyzeChatTitle(question);
    if(!suggestion.provisional)return suggestion.title;
    provisional ||= suggestion;
  }
  return provisional?.title||"Chat baru";
}
export function resolveChatTitle(room:{title:string;titleEdited?:boolean},questions:string[]):string {
  return room.titleEdited?room.title:suggestChatTitle(questions);
}

/** Local commands never become model requests or persisted messages. */
export function getLocalChatCommand(input:string):"context"|null {return input.trim().toLowerCase()==="/context"?"context":null;}
