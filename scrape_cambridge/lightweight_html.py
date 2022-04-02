import re
import os
import concurrent.futures


SCRIPT_PATTERN = re.compile(r"(<script(.|\n)*?</script>)|(<noscript(.|\n)*?</noscript>)|(<style(.|\n)*?</style>)|(<amp(.|\n)*?</amp.*?>)|(<meta.*?>)|(<link.*?>)")
NEW_LINE_PATTERN = re.compile(" *\r*\n[\r\n ]*")
test = """<script type="text/javascript">
function OptanonWrapper() { }
</script>

<script type='text/javascript'>
function readCookie(name) {
var nameEQ = name + "=";
var ca = document.cookie.split(';');
for ( var i = 0; i < ca.length; i++) {
var c = ca[i];
while (c.charAt(0) == ' ')
c = c.substring(1, c.length);
if (c.indexOf(nameEQ) == 0)
return c.substring(nameEQ.length, c.length);
}
return null;
}
var pl_did = readCookie("pl_did");
var pl_p = localStorage.pl;
</script> erkjeregr<script type='text/javascript'>




<meta itemprop="headline" content="ad-supported software definition: &rarr;&nbsp;adware. Learn more." />
<meta itemprop="headline" content="ad-supported software definition: &rarr;&nbsp;adware. Learn more." />
<meta itemprop="headline" content="ad-supported software definition: &rarr;&nbsp;adware. Learn more." />

fwe

few

        <style>
        .i-amphtml-element>[overflow] {
           display: block !important;
        }
        </style>

<meta itemprop="headline" content="ad-supported software definition: &rarr;&nbsp;adware. Learn more." />
</script>
fwfw
    <amp-state id="stateGlobal">
    <script type="application/json">
    {
        "imageCredits": "",
        "flyout": "",
        "wlSenseId": "",
        "modal": ""
    }
    </script>\n\n\n\n        
</amp-state>
fwef                         wen\n\n\n\n\nsdf



<title>2:1 | meaning in the Cambridge English Dictionary</title>










































































































</head>

<body class="break default_layout" >
<div id="top"></div>






<header id="header" class="pf ch q250 lc1" [class]="stateHdr.search && stateHdr.searchDesk ? 'pf ch ch-hs lc1' : 'pf ch q250 lc1'">



<div class="pr bh lcs z1 fon hdf" role="button" on="tap: AMP.setState({ stateSearch: { autocomplete: false } })" aria-label="Close autocomplete" tabindex="0">



<div class="hoh flx-w_no">

<div class="hfl">

<div class="hdib hv-3 lpt-15 lpl-15 lpr-15 lp-l_l-25">

<a class="cb hao lpt-2" on="tap:AMP.setState({ stateSearch: { autocomplete: false } }), sidebarNav.open"

role="button" aria-label="Open site navigation panel" tabindex="0"><i></i></a>

</div>



<div class="hdib hvt hao tc-bd lpt-10 lpb-2 lpr-15 lbr-s lb-ch ">

<a class="hdib lpb-5 lpt-1 " href="/" title="Cambridge Dictionary">





</a>

</div>

</div>

"""


def lightweight(file_content):
    trash_free_content = re.sub(SCRIPT_PATTERN, "", file_content)
    fixed_height_new_line_content = re.sub(NEW_LINE_PATTERN, "\n", trash_free_content)
    return fixed_height_new_line_content.strip()

# test = "<script>\n\n\n\n\n</script>\n\n\n\n\n         fsdfs   \n    \n\n\n sdfsdfs  sdfs"
print(lightweight(test).split(sep="\n"))
# print(re.sub(NEW_LINE_PATTERN, "\n", ))

quit()


def get_file_content(path):
    with open(path, "r", encoding="utf-8") as f:
        return path, f.read()


def write_lighter_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


executor = concurrent.futures.ThreadPoolExecutor()

base = os.path.expanduser("~/Desktop/dict")
for page_index in os.listdir(base)[::-1]:
    folder = os.path.join(base, page_index)

    folder_containments = os.listdir(folder)

    last_log_length = 0
    section_logs = ("current folder %\\\\", "current folder % //")
    
    step = 1
    for batch_start in range(0, len(folder_containments), step):
        log_string = f"\r{section_logs[batch_start % 2]}{batch_start / len(folder_containments) * 100: .2f}%"
        print("\r" + " " * last_log_length, end="")
        print(log_string, end="")
        last_log_length = len(log_string)

        # get_content_futures = []
        # for i in range(batch_start, min(len(folder_containments), batch_start+step)):
        #     path = os.path.join(folder, folder_containments[batch_start+i])
        #     get_content_futures.append(executor.submit(get_file_content, path))

        get_content_futures = executor.map(get_file_content, [os.path.join(folder, fname) for fname in folder_containments[batch_start:batch_start+step]])
        refresh_file_futures = []
        for path, content in get_content_futures:
            content = lightweight(content)
            refresh_file_futures.append(executor.submit(write_lighter_file, path, content))
        
        for write_future in concurrent.futures.as_completed(refresh_file_futures):
            write_future.result()
        quit()