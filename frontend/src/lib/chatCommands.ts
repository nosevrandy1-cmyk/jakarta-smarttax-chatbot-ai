export const CHAT_COMMANDS=[{command:"/context",label:"Konteks",description:"Lihat sisa kapasitas percakapan"}] as const;
export function getCommandSuggestions(input:string){
  const prefix=input.trim().toLowerCase();
  if(!prefix.startsWith("/") || /\s/.test(prefix))return [];
  return CHAT_COMMANDS.filter(item=>item.command.startsWith(prefix));
}
export function resolveCommandInput(input:string):string|null {
  const matches=getCommandSuggestions(input);
  return matches.length===1?matches[0].command:null;
}
