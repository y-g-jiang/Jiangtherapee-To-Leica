import argparse,concurrent.futures,os,re,shutil,subprocess
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('arch',choices=['win','arm64','x86_64']);parser.add_argument('raw',type=Path);parser.add_argument('zlib',type=Path);parser.add_argument('jpeg',type=Path);parser.add_argument('work',type=Path);parser.add_argument('--zig');args=parser.parse_args()
here=Path(__file__).resolve().parent;raw=args.raw.resolve();zlib=args.zlib.resolve();jpeg=args.jpeg.resolve();build=args.work.resolve()/args.arch;build.mkdir(parents=True,exist_ok=True)
commit=subprocess.check_output(['git','-C',str(raw),'rev-parse','HEAD'],text=True).strip() if (raw/'.git').exists() else (raw/'JTL-COMMIT').read_text().strip()
if commit!='40fb564486681a04eba0318058b0519f4f69eba8':raise ValueError('Unexpected upstream revision')
manifest=(raw/'Makefile.dist').read_text();names=re.search(r'LIB_OBJECTS= (.*?)\n\n',manifest,re.S)[1];sources={name:path for name,path in re.findall(r'^object/([\w]+)\.o:\s*(src/\S+\.cpp)',manifest,re.M)}
inputs=[raw/sources[name] for name in re.findall(r'object/(\w+)\.o',names)];inputs.append(here/'jtl_raw.cpp')
inputs.extend(zlib/(name+'.c') for name in 'adler32 compress crc32 deflate gzclose gzlib gzread gzwrite infback inffast inflate inftrees trees uncompr zutil'.split())
jpegs=re.search(r'^LIBSOURCES = (.*?)\n\n',(jpeg/'Makefile.am').read_text(),re.M|re.S)[1].replace('@MEMORYMGR@','jmemnobs');inputs.extend(jpeg/name for name in re.findall(r'(\w+\.c)',jpegs));windows=args.arch=='win'
shutil.copyfile(jpeg/('jconfig.vc' if windows else 'jconfig.xc'),build/'jconfig.h')
flags=['-O2','-w','-DNDEBUG','-DLIBRAW_NODLL','-DUSE_ZLIB','-DUSE_JPEG','-DUSE_JPEG8',f'-DJTL_COMMIT="{commit}"','-I'+str(raw),'-I'+str(zlib),'-I'+str(build),'-I'+str(jpeg)]
def compiler(cpp):
    if windows:return [os.environ.get('CXX' if cpp else 'CC','C:/Program Files/LLVM/bin/clang'+('++' if cpp else '')+'.exe')]
    return [str(Path(args.zig).resolve()),'c++' if cpp else 'cc','-target',('aarch64' if args.arch=='arm64' else 'x86_64')+'-macos.13.3','-fno-sanitize=all','-fPIC']
def compile_one(source):
    target=build/(source.stem+'.o');cpp=source.suffix=='.cpp'
    if not target.exists() or target.stat().st_mtime<max(source.stat().st_mtime,Path(__file__).stat().st_mtime):
        extra=['-DHAVE_UNISTD_H'] if not windows and source.parent==zlib else []
        subprocess.run(compiler(cpp)+flags+extra+(['-std=c++14'] if cpp else [])+['-c',str(source),'-o',str(target)],check=True)
    return target
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:objects=list(pool.map(compile_one,inputs))
output=here.parent/('jtl-libraw-'+args.arch+('.dll' if windows else '.dylib'));options=['-shared','-Wl,/implib:'+str(build/'libraw.lib')] if windows else ['-dynamiclib','-Wl,-install_name,@rpath/'+output.name]
subprocess.run(compiler(True)+options+list(map(str,objects))+['-o',str(output)],check=True);print(commit,output,output.stat().st_size,flush=True)
