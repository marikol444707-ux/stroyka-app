from pathlib import Path
import subprocess,json,hashlib,os
p=Path(__file__).parent;out=p/'realism-film-chapters';out.mkdir(exist_ok=True)
rows=[]
def add(title,caption,frames,crop=False):rows.append({'title':title,'caption':caption,'frames':frames,'crop':crop})
def still(name,seconds):return [(name,seconds)]
add('Дом в окружении\nзелени','Шесть деревьев и посадки вокруг дома.\nОзеленение показано как идея.',still('realism-exterior-large.png',3))
add('Больше комнаты\nв кадре','Расширили интерьерный ракурс.\nПоложение мебели сохранено.',still('realism-living-large.png',3))
add('Ткань и форма\nмягких деталей','Две подушки того же дивана\nполучили более мягкую форму и ткань.',still('realism-living-large.png',3))
add('Днём и вечером','Та же кухня и обеденная зона.\nСвет можно переключать отдельно.',[('realism-kitchen-large.png',2),('realism-evening-large.png',2)])
add('Вид из окна:\nбыло и стало','Та же модель и тот же ракурс.\nДвор появляется в реальной 3D-сцене.',[('realism-window-before.png',2),('realism-window-large.png',2)])
add('Прогулка\nс телефона','Повороты сглажены; при уменьшении\nдвижения сглаживание отключается.',still('realism-window-mobile.png',3))
(p/'realism-film-storyboard.json').write_text(json.dumps({'chapters':rows,'source':'Actual v25/v26 browser UI and native model captures; editorial walkthrough, not measured device FPS.'},ensure_ascii=False,indent=2))
(p/'realism-film-brand.txt').write_text('СТРОЙКА / ДОМ 01 · ОКРУЖЕНИЕ И ДЕТАЛИ');(p/'realism-film-footer.txt').write_text('Архитектурный эскиз · требует согласования')
env=os.environ.copy();env['XDG_CACHE_HOME']=str(p/'cache')
for i,c in enumerate(rows,1):
 stem=out/f'{i:02d}'
 for key in ['title','caption']:stem.with_suffix('.'+key+'.txt').write_text(c[key])
 frames=c['frames'];stem.with_suffix('.list').write_text(''.join("file '"+str(p/name)+"'\nduration "+str(d)+'\n' for name,d in frames)+"file '"+str(p/frames[-1][0])+"'\n")
 vf=("crop=iw:trunc(ih*.65/2)*2:0:ih-trunc(ih*.65/2)*2," if c['crop'] else '')+"scale=720:600:force_original_aspect_ratio=decrease,setsar=1,pad=720:1000:(ow-iw)/2:220+(600-ih)/2:color=0xf5f4ee,fps=24,scale=in_range=pc:out_range=tv,format=yuv420p,"
 vf+=f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:textfile={p/'realism-film-brand.txt'}:expansion=none:fontsize=20:fontcolor=0x67765e:x=40:y=35,drawbox=x=40:y=76:w=76:h=3:color=0xac6b43:t=fill,"
 vf+=f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf:textfile={stem.with_suffix('.title.txt')}:expansion=none:fontsize=43:fontcolor=0x26372f:x=40:y=104:line_spacing=8,"
 vf+=f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:textfile={stem.with_suffix('.caption.txt')}:expansion=none:fontsize=21:fontcolor=0x42573e:x=40:y=855:line_spacing=10,"
 vf+=f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:textfile={p/'realism-film-footer.txt'}:expansion=none:fontsize=16:fontcolor=0x75816a:x=40:y=966"
 duration=sum(d for name,d in frames)
 subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(stem.with_suffix('.list')),'-vf',vf,'-t',str(duration),'-c:v','libx264','-threads','2','-profile:v','baseline','-level','4.0','-preset','medium','-crf','21','-color_range','tv','-movflags','+faststart','-an',str(stem.with_suffix('.mp4'))],check=True,env=env);print('CHAPTER',i,flush=True)
(out/'concat.list').write_text(''.join("file '"+str(out/f'{i:02d}.mp4')+"'\n" for i in range(1,len(rows)+1)))
video=p/'realism.mp4';subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(out/'concat.list'),'-c','copy','-movflags','+faststart',str(video)],check=True)
with (p/'realism-film-decode.log').open('w') as err:subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','-'],stdout=subprocess.DEVNULL,stderr=err,check=True)
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]));v=probe['streams'][0];assert v['codec_name']=='h264' and v['profile']=='Constrained Baseline' and v['pix_fmt']=='yuv420p'
result={'passed':True,'file':video.name,'seconds':float(probe['format']['duration']),'bytes':video.stat().st_size,'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'codec':'h264 baseline yuv420p','width':v['width'],'height':v['height'],'fps':v['r_frame_rate'],'chapters':len(rows),'source':'Actual v25/v26 browser captures; editorial walkthrough, not a continuous recording or device FPS benchmark.'}
(p/'realism-film-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
subprocess.run(['ffmpeg','-y','-v','error','-ss','7','-i',str(video),'-frames:v','1',str(p/'realism-preview.png')],check=True)

subprocess.run(['ffmpeg','-y','-v','error','-i',str(video),'-filter_complex','[0:v]fps=8,scale=360:500:flags=lanczos,split[a][b];[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle','-loop','0',str(p/'realism.gif')],check=True)
subprocess.run(['ffmpeg','-v','error','-i',str(p/'realism.gif'),'-f','null','-'],check=True)

gif=p/'realism.gif'
gif_probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_entries','stream=codec_name,width,height,nb_read_frames:format=duration,size','-of','json',str(gif)]))
result['gif']={'seconds':float(gif_probe['format']['duration']),'bytes':gif.stat().st_size,'sha256':hashlib.sha256(gif.read_bytes()).hexdigest(),'frames':int(gif_probe['streams'][0]['nb_read_frames']),'width':360,'height':500,'decoded':True}
(p/'realism-film-validation.json').write_text(json.dumps(result,indent=2))

