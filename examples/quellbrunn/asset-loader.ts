export async function loadImage(url:string){const image=new Image();image.src=url;await image.decode();return image;}
