/** Fit complete words only. The stored title is never changed by layout. */
export function fitTitleToWidth(title:string,width:number,measure:(text:string)=>number):string {
  if(width<=0)return "";
  if(measure(title)<=width)return title;
  const words=title.trim().split(/\s+/);let result="";
  for(const word of words){
    const next=result?`${result} ${word}`:word;
    if(measure(next+"…")>width)break;
    result=next;
  }
  return result?result+"…":measure("…")<=width?"…":"";
}
