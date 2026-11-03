/** Defensive rendering for responses saved before malformed metadata was handled. */
export function presentAssistantMessage<T extends {role:string;content:string;followUps?:string[];originalQuestion?:string}>(message:T):T {
  if(message.role!=="assistant")return message;
  const marker=/(?:<|&lt;)\s*JST_FOLLOW_UPS\b/i.exec(message.content);
  if(!marker)return message;
  const answer=message.content.slice(0,marker.index).trimEnd();
  const tail=message.content.slice(marker.index+marker[0].length);
  let followUps:string[]=[];
  const closing=/(?:<|&lt;)\/JST_FOLLOW_UPS\s*(?:>|&gt;)?/i.exec(tail);
  if(closing){
    let payload=tail.slice(0,closing.index).trim().replace(/^(?:>|&gt;)\s*/,"");
    try{
      const raw:unknown=JSON.parse(payload);
      const key=(text:string)=>text.toLocaleLowerCase().replace(/[^\p{L}\p{N}]/gu,"");
      const seen=new Set([key(message.originalQuestion||"")]);
      if(Array.isArray(raw))for(const value of raw.slice(0,8)){
        if(typeof value!=="string")continue;
        const text=value.replace(/\s+/g," ").trim();
        if(text.length<8||text.length>160||seen.has(key(text))||/https?:|www\.|[<>]|data:|base64|^\/|\[\d+\]|\b(unggah|upload|lampirkan|unduh|download)\b|kirim(?:kan)?\s+(file|dokumen)/i.test(text))continue;
        seen.add(key(text));followUps.push(text);if(followUps.length===2)break;
      }
    }catch{/* Keep the answer readable even when optional metadata is invalid. */}
  }
  return {...message,content:answer,followUps:message.followUps?.length?message.followUps:followUps};
}
