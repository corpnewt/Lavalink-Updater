from Scripts import utils, downloader
import os, json, subprocess, re, tempfile, shutil, time, datetime, argparse

LAVALINK_URL  = "https://github.com/lavalink-devs/Lavalink/releases/{}"
LAVALINK_REG = re.compile(r"(?i)Lavalink\.jar")
LAVALINK_KEY = "Lavalink"
YTSOURCE_URL = "https://github.com/lavalink-devs/youtube-source/releases/{}"
YTSOURCE_REG = re.compile(r"(?i)youtube-plugin-([0-9a-z]\.?)+\.jar")
YTSOURCE_KEY = "youtube-source"

DOC_URL = "https://lavalink.dev/configuration/index.html"

LAVALINK_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),"Lavalink.jar")
YML_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),"application.yml")

u = utils.Utils("Lavalink Starter")

DL = None
try: DL = downloader.Downloader()
except: pass

PROC_REG = re.compile(r"(?i).*(?P<process>javaw?(\.exe)?)(\s*\")?(?P<arguments>(\s.*|\s)+(?P<jar>-jar)\s+.*(?P<lavalink>Lavalink\.jar))")

def check_yts_version(yml_file):
    yts_version = None
    if not yml_file or not os.path.isfile(yml_file):
        return yts_version
    with open(yml_file) as f:
        yml_data = f.read()
    for line in yml_data.split("\n"):
        if not line.strip().startswith("#") and \
        "- dependency:" in line and \
        "dev.lavalink.youtube:youtube-plugin:" in line:
            # We found it - save the version
            yts_version = line.split("dev.lavalink.youtube:youtube-plugin:")[-1].strip('"')
            break
    return yts_version

def update_yts_version(yml_file,version):
    if not yml_file or not os.path.isfile(yml_file):
        return False
    with open(yml_file) as f:
        yml_data = f.read()
    new_data = []
    found = False
    for line in yml_data.split("\n"):
        if not line.strip().startswith("#") and \
        "- dependency:" in line and \
        "dev.lavalink.youtube:youtube-plugin:" in line:
            # We found it - save the version
            yts_version = line.split("dev.lavalink.youtube:youtube-plugin:")[-1].strip('"')
            line = line.replace(yts_version,version)
            found = True
        new_data.append(line)
    if not found:
        return False
    with open(yml_file,"w") as f:
        f.write("\n".join(new_data))
    return True

def check_lavalink_version(lavalink_file):
    lavalink_version = None
    if not lavalink_file or not os.path.isfile(lavalink_file):
        return None
    if not JAVA_PATH:
        return None
    # Let's try to get the version via java -jar Lavalink.jar --version
    try:
        p = subprocess.run(
            [JAVA_PATH,"-jar",lavalink_file,"--version"],
            check=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        lavalink_output = p.stderr.decode("utf-8").replace("\r","") + "\n" + p.stdout.decode("utf-8").replace("\r","")
        for line in lavalink_output.split("\n"):
            if line.lower().strip().startswith("version:"):
                return ":".join(line.split(":")[1:]).strip()
    except:
        pass
    return None

def get_latest_info(key, url, regex_search):
    # Get whatever we have stored in the settings from our last
    # successful download
    # Scrape the latest version from the url
    try:
        html = DL.get_string(url,progress=False)
    except:
        html = None
    if not html:
        # Return Success/Fail, version, URL
        return (False,None,None)
    # Check for expanded assets and version number
    asset_html = version = None
    try:
        asset_url = next((x.split('src="')[1].split('"')[0] for x in html.split("\n") if "expanded_assets" in x),None)
        assert asset_url
        version = asset_url.split("/")[-1]
        asset_html = DL.get_string(asset_url,progress=False)
    except:
        pass
    if not asset_html:
        # Return Success/Fail, version, URL
        return (False,None,None)
    # Try to scrape the assets for our regex_search
    asset = None
    for line in asset_html.split("\n"):
        if '<a href="' in line:
            try:
                asset_url = "https://github.com"+line.split('<a href="')[1].split('"')[0]
                if regex_search.fullmatch(asset_url.split("/")[-1]):
                    asset = asset_url
                    break
            except: continue
    if version and asset:
        return (True,version,asset)
    return (False,version,asset)

def get_bin_path(binary):
    bin_path = None
    try:
        p = subprocess.run(
            ["where" if os.name == "nt" else "which",binary],
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE
        )
        bin_path =  p.stdout.decode("utf-8").replace("\r","").split("\n")[0]
    except:
        pass
    return bin_path

def check_pids(prompt_answer = None):
    # Gather a list of PIDs for java apps that appear to be running lavalink
    # and ask the user if they want to auto-kill them, ignore, or they can just
    # press enter to refresh the list.
    if prompt_answer is not None:
        # Make sure it's a valid option - or reset it
        if not prompt_answer in ("y","n","q"):
            prompt_answer = None
    while True:
        pids = get_pids(include_comm=True)
        if not pids: # Nothing matched our checks - just bail
            return (prompt_answer,False)
        if prompt_answer is not None:
            prompt = prompt_answer
        else:
            # We got at least one potential PID - let's prompt the user
            u.head("Lavalink Already Running")
            print("")
            print("The following PID(s) appear to be running Lavalink:\n")
            pid_width = len(max(str(x[1]) for x in pids))
            for c,p in pids:
                print(" - {} | {} {}".format(str(p).rjust(pid_width),c.group("process"),c.group("arguments").strip()))
            print("")
            print("Multiple instances of Lavalink that use the same port will conflict.")
            try:
                prompt = u.grab("Would you like to terminate them? ([y]es/[n]o/[q]uit):  ")
            except KeyboardInterrupt:
                exit()
            if not len(prompt):
                continue
        # We should have our prompt at this point
        if not prompt in ("y","n","q"):
            continue
        if prompt == "q":
            exit()
        elif prompt == "y":
            # Let's iterate them and kill them individually
            if prompt_answer is None:
                u.head("Killing Lavalink Processes")
                print("")
            for c,p in pids:
                print("Killing PID {}...".format(p))
                returncode = kill_pid(p)
                if returncode == 0:
                    print(" - Killed")
                else:
                    print(" - Failed with return code {}".format(returncode))
                    print("")
                    try: u.grab("Press [enter] to exit...")
                    except KeyboardInterrupt: pass
                    exit(returncode)
        # If we got here - we're not killing PIDs, or 
        # they should all be dead - return our answer
        # so that we can re-use it as needed
        return (prompt,prompt_answer is None)

def kill_pid(pid):
    timeout = 10 # Allow up to 10 seconds to kill
    # Automate taskkill or kill based on os
    comm = ["taskkill","/f","/pid",str(pid),"/t"] if os.name=="nt" else ["kill",str(pid)]
    p = subprocess.Popen(comm,stderr=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
    try:
        p.communicate() # Wait for it to complete
    except KeyboardInterrupt:
        print("\n - Keyboard interrupt, exiting...\n")
        exit()
    if p.returncode != 0:
        return p.returncode # Something went wrong killing it
    # Verify it closed on a timed loop
    wait_start = time.time()
    while True:
        if not get_pids(pid=pid):
            break # No longer running
        if time.time() - wait_start >= timeout:
            return -1 # We waited too long
        time.sleep(0.05)
    return 0

def get_pids(pid = None, include_comm = False):
    # Helper to extract the PIDs/commands of any instances of java that are
    # running Lavalink.jar - or to optionally check if a particular PID still
    # exists.
    pids = []
    if os.name == "nt":
        if USE_WMIC:
            comm = ["wmic","process","where","name like '%java%'","get","processid,commandline"]
        else:
            comm = ["powershell","-c","Get-WmiObject win32_process -Filter \"name like '%java%'\"|select ProcessId,CommandLine|ft -AutoSize|Out-String -width 9999999"]
    else:
        comm = ["ps","aux"]
    try:
        p = subprocess.run(
            comm,
            check=True,
            stderr=subprocess.DEVNULL,
            stdout=subprocess.PIPE
        )
        procs = p.stdout.decode("utf-8").replace("\r","")
        for line in procs.split("\n"):
            # Check if it's got valid command output
            m = COMMAND_REG.fullmatch(line)
            if not m: continue
            if pid is not None:
                # Checking for a specific PID
                if m.group("pid").strip() != pid:
                    continue
            else:
                # See if we have java(w)(.exe) -jar Lavalink.jar to
                # reasonably assume we've found it
                c = PROC_REG.fullmatch(m.group("command").strip())
                if not c: continue
            # Found it - retain it
            pids.append(
                # Save a tuple of (command match, PID) or just PID depending on settings
                (c,m.group("pid").strip()) if include_comm else m.group("pid").strip()
            )
    except:
        pass
    return pids

def print_line(lines,text):
    print(text)
    lines.append(text)
    return lines

def main(skip_git = False, list_update = False, update = True, only_update = False, force = False, force_if_different = False, prompt_answer = None, l_target = None, y_target = None):
    if not skip_git:
        git = get_bin_path("git")
        if git:
            # Try our update
            updated = False
            cwd = os.getcwd()
            os.chdir(os.path.dirname(os.path.realpath(__file__)))
            try:
                p = subprocess.run(
                    git,
                    check=True,
                    stderr=subprocess.DEVNULL,
                    stdout=subprocess.PIPE
                )
                if not "up to date" in p.stdout.decode("utf-8"):
                    updated = True
            except:
                pass
            os.chdir(cwd)
            if updated:
                # Restart ourselves via subprocess
                p = subprocess.Popen([sys.executable,os.path.realpath(__file__)]+sys.argv[1:])
                p.communicate()
                exit(p.returncode)
    if list_update:
        print("Local versions:")
        yts_version = check_yts_version(YML_PATH)
        print(" - YouTube-Source: {}".format(yts_version or "MISSING"))
        ll_version = check_lavalink_version(LAVALINK_PATH)
        print(" - Lavalink: {}".format(ll_version or ("JAVA MISSING" if not JAVA_PATH else "MISSING")))
        print("Remote versions:")
        # Only checking for updates - gather them and report
        y_success,y_version,y_ulr = get_latest_info(YTSOURCE_KEY,YTSOURCE_URL.format("latest"),YTSOURCE_REG)
        if not y_success:
            print(" - YouTube-Source: Error checking for updates")
        else:
            print(" - YouTube-Source: {}".format(y_version))
        l_success,l_version,l_url = get_latest_info(LAVALINK_KEY,LAVALINK_URL.format("latest"),LAVALINK_REG)
        if not l_success:
            print(" - Lavalink: Error checking for updates")
        else:
            print(" - Lavalink: {}".format(l_version))
        # Print if either needs an update
        if y_version or l_version:
            print("")
        if y_version:
            if yts_version is None or u.compare_versions(yts_version,y_version):
                print("YouTube-Source update available")
            else:
                print("YouTube-Source is up to date")
        if l_version:
            if ll_version is None or u.compare_versions(ll_version,l_version):
                print("Lavalink update available")
            else:
                print("Lavalink is up to date")
        exit()
    u.head()
    lines = print_line([],"\n{}: Starting Lavalink update...\n".format(datetime.datetime.now().time().isoformat()))
    lines = print_line(lines,"Gathering info...")
    # First check for java
    if not JAVA_PATH:
        print("Could not locate java!")
        print("")
        try: u.grab("Press [enter] to exit...")
        except KeyboardInterrupt: pass
        exit(1)
    # Let's verify if we have an application.yml or not - and inform the user
    if not os.path.isfile(YML_PATH):
        print("{} not found!\n".format(YML_PATH))
        print("Please visit the following link to create one:")
        print(" - {}\n".format(DOC_URL))
        try: u.grab("Press [enter] to exit...")
        except KeyboardInterrupt: pass
        exit()
    # Scrape the version
    lines = print_line(lines,"Gathering local versions...")
    yts_version = check_yts_version(YML_PATH)
    lines = print_line(lines," - YouTube-Source: {}".format(yts_version or "MISSING"))
    if not yts_version:
        print("\nCould not locate youtube-plugin information in")
        print(" - {}".format(YML_PATH))
        print("")
        print("Please visit the following link for info:")
        print(" - {}\n".format(DOC_URL))
        try: u.grab("Press [enter] to exit...")
        except KeyboardInterrupt: pass
        exit()
    # Let's check for updates now
    ll_version = check_lavalink_version(LAVALINK_PATH)
    lines = print_line(lines," - Lavalink: {}".format(ll_version or "MISSING"))
    # Lavalink first
    if only_update or update:
        # If we're only forcing when different - check if they're not equal,
        # otherwise check for remote > local
        allowed_comparisons = (True,False) if force_if_different else (True,)
        lines = print_line(lines,"Gathering remote versions...")
        y_success,y_version,y_ulr = get_latest_info(YTSOURCE_KEY,YTSOURCE_URL.format(y_target or "latest"),YTSOURCE_REG)
        if not y_success:
            lines = print_line(lines," - YouTube-Source: Error checking for updates")
        else:
            lines = print_line(lines," - YouTube-Source: {}".format(y_version))
        l_success,l_version,l_url = get_latest_info(LAVALINK_KEY,LAVALINK_URL.format(l_target or "latest"),LAVALINK_REG)
        if not l_success:
            lines = print_line(lines," - Lavalink: Error checking for updates")
        else:
            lines = print_line(lines," - Lavalink: {}".format(l_version))
        if l_version and (force or ll_version is None or u.compare_versions(ll_version,l_version) in allowed_comparisons):
            lines = print_line(lines,"\n{}Updating Lavalink...".format("Force-" if force or force_if_different else ""))
            lines = print_line(lines,"")
            lines = print_line(lines,"Downloading {} ({})...".format(os.path.basename(l_url),l_version))
            temp = tempfile.mkdtemp()
            try:
                ll_temp = DL.stream_to_file(l_url,os.path.join(temp,os.path.basename(l_url)))
                assert ll_temp is not None
                # Kill the running instance if any
                if not only_update:
                    prompt_answer,printed = check_pids(prompt_answer=prompt_answer)
                    if printed:
                        # Re-print our prior lines
                        u.head()
                        print("\n".join(lines))
                # Remove the current file and move the new one over
                lines = print_line(lines,"Moving {} into place...".format(os.path.basename(l_url)))
                shutil.move(ll_temp,LAVALINK_PATH)
                lines = print_line(lines,"Updated {} to {}".format(os.path.basename(l_url),l_version))
            except Exception as e:
                lines = print_line(lines,"Update failed: {}".format(e))
            finally:
                shutil.rmtree(temp,ignore_errors=True)
        if y_version and (force or u.compare_versions(yts_version,y_version) in allowed_comparisons):
            lines = print_line(lines,"\n{}Updating YouTube-Source...".format("Force-" if force or force_if_different else ""))
            if not update_yts_version(YML_PATH,y_version):
                lines = print_line(lines,"Update failed - please verify your application.yml!")
            else:
                lines = print_line(lines,"Updated YouTube-Source to {}".format(y_version))
    if only_update:
        # Bail here
        exit()
    # Kill the running instance if any
    prompt_answer,printed = check_pids(prompt_answer=prompt_answer)
    if printed:
        # Re-print our prior lines
        u.head()
        print("\n".join(lines))
    # Start the new version as needed
    print("\nStarting Lavalink.jar...")
    if not os.path.isfile(LAVALINK_PATH):
        print(" - File does not exist!\n")
        try: u.grab("Press [enter] to exit...")
        except KeyboardInterrupt: pass
        exit()
    print("")
    cwd = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    lavalink = subprocess.Popen([JAVA_PATH,"-jar",LAVALINK_PATH])
    os.chdir(cwd)
    try:
        lavalink.communicate()
    except KeyboardInterrupt:
        print("\n - Keyboard interrupt, exiting...\n")
        exit()
    exit(lavalink.returncode)

JAVA_PATH = get_bin_path("java")
USE_WMIC = get_bin_path("wmic")
if os.name == "nt":
    if USE_WMIC:
        COMMAND_REG = re.compile(r"(?i)(?P<command>.*)\s+(?P<pid>\d+).*")
    else:
        COMMAND_REG = re.compile(r"(?i)\s*(?P<pid>\d+)\s+(?P<command>.*)")
else:
    COMMAND_REG = re.compile(r"(?i)([^\s]+\s+)(?P<pid>\d+)\s+([^\s]+\s+){8}(?P<command>.*)")

if __name__ == "__main__":
    # Setup the cli args
    parser = argparse.ArgumentParser(prog="Lavalink.py", description="Lavalink.py - a py script to update and launch Lavalink.jar")
    parser.add_argument("-c", "--check-updates", help="only report the latest Lavalink and YouTube-Source versions (overrides all but --help)", action="store_true")
    parser.add_argument("-l", "--lavalink-version", help="update Lavalink.jar to the passed version tag instead of \"latest\" if it exists (requires --force[-if-different] if passing an older version)")
    parser.add_argument("-y", "--yts-version", help="update YouTube-Source to the passed version tag instead of \"latest\" if it exists (requires --force[-if-different] if passing an older version)")
    parser.add_argument("-f", "--force", help="force Lavalink.jar and YouTube-Source updates (overrides --force-if-different)", action="store_true")
    parser.add_argument("-d", "--force-if-different", help="force Lavalink.jar and YouTube-Source updates only if the local and remote versions are different", action="store_true")
    parser.add_argument("-s", "--skip-updates", help="skip update checks (overrides --force)", action="store_true")
    parser.add_argument("-o", "--only-update", help="only update, don't start Lavalink (overrides --skip-updates)", action="store_true")
    parser.add_argument("-g", "--skip-git", help="GitHub self updates", action="store_true")
    parser.add_argument("-r", "--handle-running", help="how to handle detected currently running Lavalink.jar instances", choices=["kill","ignore","quit","ask"], default="ask")

    args = parser.parse_args()

    prompt_dict = {"kill":"y","ignore":"n","quit":"q"}
    main(
        skip_git=args.skip_git,
        list_update=args.check_updates,
        update=not args.skip_updates,
        only_update=args.only_update,
        force=args.force,
        force_if_different=args.force_if_different,
        prompt_answer=prompt_dict.get(args.handle_running),
        l_target=args.lavalink_version,
        y_target=args.yts_version
    )
