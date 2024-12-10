from Scripts import utils, downloader
import os, sys, json, subprocess, re, tempfile, shutil, time, datetime, argparse

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

LAVALINK_URL = "https://github.com/lavalink-devs/Lavalink/releases/{}"
LAVALINK_API = "https://api.github.com/repos/lavalink-devs/Lavalink/releases/{}"
LAVALINK_REG = re.compile(r"(?i)^Lavalink\.jar$")
YTSOURCE_URL = "https://github.com/lavalink-devs/youtube-source/releases/{}"
YTSOURCE_API = "https://api.github.com/repos/lavalink-devs/youtube-source/releases/{}"
YTSOURCE_REG = re.compile(r"(?i)^youtube-plugin-([0-9a-z]\.?)+\.jar$")

DOC_URL = "https://lavalink.dev/configuration/index.html"

LAVALINK_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),"Lavalink.jar")
YML_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),"application.yml")

u = utils.Utils("Lavalink Updater")

DL = None
try: DL = downloader.Downloader()
except: pass

PROC_REG = re.compile(r"(?i)^.*(?P<process>javaw?(\.exe)?)(\s*\")?(?P<arguments>(\s.*|\s)+(?P<jar>-jar)\s+.*(?P<lavalink>Lavalink\.jar)\s*\"?)$")

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

def check_plugin_dir(yml_file):
    if not yml_file or not os.path.isfile(yml_file):
        return None
    with open(yml_file) as f:
        yml_data = f.read()
    plugin_dir = None
    for line in yml_data.split("\n"):
        if line.lstrip().startswith("pluginsDir: "):
            # Rip the plugin directory if found
            plugin_dir = "pluginsDir: ".join(line.lstrip().split("pluginsDir: ")[1:])
            if plugin_dir[0] == plugin_dir[-1] == '"':
                # Got quotes
                plugin_dir = plugin_dir[1:-1]
            # Get the real path
            try:
                cwd = os.getcwd()
                os.chdir(os.path.dirname(os.path.realpath(__file__)))
                plugin_dir = os.path.realpath(plugin_dir)
            except Exception:
                return None
            finally:
                os.chdir(cwd)
            break
    # Fall back on the default path of ./plugins
    return plugin_dir or os.path.join(os.path.dirname(os.path.realpath(__file__)),"plugins")

def update_yts_version(yml_file,version,temp):
    if not yml_file or not os.path.isfile(yml_file):
        return None
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
        return None
    temp_yml = os.path.join(temp,os.path.basename(yml_file))
    with open(temp_yml,"w") as f:
        f.write("\n".join(new_data))
    return temp_yml

def check_lavalink_version(lavalink_file):
    lavalink_version = None
    if not lavalink_file or not os.path.isfile(lavalink_file):
        return None
    if not JAVA_PATH:
        return None
    # Let's try to get the version via java -jar Lavalink.jar --version
    try:
        p = subprocess.Popen(
            [JAVA_PATH,"-jar",lavalink_file,"--version"],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        o,e = p.communicate()
        assert p.returncode == 0
        lavalink_output = o.decode("utf-8").replace("\r","") + "\n" + e.decode("utf-8").replace("\r","")
        for line in lavalink_output.split("\n"):
            if line.lower().strip().startswith("version:"):
                return ":".join(line.split(":")[1:]).strip()
    except:
        pass
    return None

def get_latest_info(html, json_api, regex_search, prioritize_html=False):
    # Prioritize HTML or the JSON API and return the first
    # successful set of results
    comms = ((get_latest_api_info,json_api),(get_latest_html_info,html))
    # Iterate in order if prioritizing the JSON api, otherwise reverse
    # the order
    for comm,url in comms[::-1 if prioritize_html else 1]:
        success,version,asset = comm(url,regex_search)
        if success:
            # If we succeeded, return the info
            return (success,version,asset)
    # If we got here, then nothing worked
    return (False,None,None)

def get_latest_api_info(url, regex_search):
    # Use the GitHub JSON API for gathering our info
    try:
        json_data = json.loads(DL.get_string(url,progress=False))
    except Exception as e:
        json_data = None
    if not json_data:
        return (False,None,None)
    # Get the version from the "tag_name" property
    # and rip the appropriate asset
    asset = version = None
    try:
        version = json_data["tag_name"]
        for a in json_data["assets"]:
            if regex_search.match(a.get("browser_download_url","").split("/")[-1]):
                asset = a["browser_download_url"]
                break
    except:
        pass
    return (version and asset,version,asset)

def get_latest_html_info(url, regex_search):
    # First check if our URL ends with "latest" - if so,
    # we should be able to build the assets URL ourselves.
    if url.lower().endswith("/latest"):
        # Let's rip the latest version just by following URL redirects
        try:
            url = DL.open_url(url).geturl()
        except:
            return (False,None,None)
    # Now we should have the target URL including the tag.  Let's
    # just rip the tag from it and try to load those assets.
    version = assets_url = asset = assets_html = None
    try:
        version = url.split("/")[-1]
        assets_url = url.split("/releases/")[0]+"/releases/expanded_assets/{}".format(version)
        assets_html = DL.get_string(assets_url,progress=False)
        assert assets_html
    except:
        return (False,version,asset)
    # Check for expanded assets and version number
    try:
        for line in assets_html.split("\n"):
            if '<a href="' in line:
                try:
                    url = "https://github.com"+line.split('<a href="')[1].split('"')[0]
                    if regex_search.match(url.split("/")[-1]):
                        asset = url
                        break
                except:
                    continue
    except:
        pass
    return (version and asset,version,asset)

def get_bin_path(binary):
    bin_path = None
    try:
        p = subprocess.Popen(
            ["where" if os.name == "nt" else "which",binary],
            stderr=getattr(subprocess,"DEVNULL",open(os.devnull,"w")),
            stdout=subprocess.PIPE
        )
        o,e = p.communicate()
        assert p.returncode == 0
        bin_path = o.decode("utf-8").replace("\r","").split("\n")[0]
    except:
        pass
    return bin_path

def cleanup(temp):
    if temp and os.path.exists(temp):
        shutil.rmtree(temp,ignore_errors=True)

def cleanexit(temp,code=0):
    cleanup(temp)
    exit(code)

def check_pids(prompt_answer=None,temp=None):
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
            print("Multiple instances of Lavalink that use the same port will conflict")
            print("and open file handles may prevent updates.")
            print("")
            try:
                prompt = u.grab("Would you like to terminate them? ([y]es/[n]o/[q]uit):  ")
            except KeyboardInterrupt:
                cleanexit(temp)
            if not len(prompt):
                continue
            prompt = prompt.lower()
        # We should have our prompt at this point
        if not prompt in ("y","n","q"):
            continue
        if prompt == "q":
            cleanexit(temp)
        elif prompt == "y":
            # Let's iterate them and kill them individually
            if prompt_answer is None:
                u.head("Killing Lavalink Processes")
                print("")
            for c,p in pids:
                # Check if the PID still corresponds to a running
                # process
                print("Verifying PID {} is still active...".format(p))
                if not get_pids(pid=p):
                    print(" - No longer active")
                    continue
                print("Killing PID {}...".format(p))
                returncode = kill_pid(p,temp=temp)
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

def kill_pid(pid,temp=None):
    timeout = 10 # Allow up to 10 seconds to kill
    # Automate taskkill or kill based on os
    comm = ["taskkill","/f","/pid",str(pid),"/t"] if os.name=="nt" else ["kill",str(pid)]
    p = subprocess.Popen(
        comm,
        stderr=getattr(subprocess,"DEVNULL",open(os.devnull,"w")),
        stdout=getattr(subprocess,"DEVNULL",open(os.devnull,"w"))
    )
    try:
        p.communicate() # Wait for it to complete
    except KeyboardInterrupt:
        print("\n - Keyboard interrupt, exiting...\n")
        cleanexit(temp)
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
        p = subprocess.Popen(
            comm,
            stderr=getattr(subprocess,"DEVNULL",open(os.devnull,"w")),
            stdout=subprocess.PIPE
        )
        o,e = p.communicate()
        assert p.returncode == 0
        procs = o.decode("utf-8").replace("\r","")
        for line in procs.split("\n"):
            # Check if it's got valid command output
            m = COMMAND_REG.match(line)
            if not m: continue
            if pid is not None:
                # Checking for a specific PID
                if m.group("pid").strip() != pid:
                    continue
            else:
                # See if we have java(w)(.exe) -jar Lavalink.jar to
                # reasonably assume we've found it
                c = PROC_REG.match(m.group("command").strip())
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

def main(
    skip_git = False,
    list_update = False,
    update = True,
    only_update = False,
    prioritize_html = False,
    force = False,
    force_if_different = False,
    prompt_answer = None,
    l_target = None,
    y_target = None
    ):
    lines = []
    if not list_update:
        # Print the header if we're doing more than listing updates
        u.head()
        lines = print_line(lines,"\n{}: Starting Lavalink update...\n".format(datetime.datetime.now().time().isoformat()))
    if not skip_git:
        # Self update check unless explicitly told to skip
        git = get_bin_path("git")
        if git:
            lines = print_line(lines,"Checking for Lavalink-Updater updates...")
            # Try our update
            updated = False
            cwd = os.getcwd()
            os.chdir(os.path.dirname(os.path.realpath(__file__)))
            try:
                p = subprocess.Popen(
                    [git,"pull"],
                    stderr=getattr(subprocess,"DEVNULL",open(os.devnull,"w")),
                    stdout=subprocess.PIPE
                )
                o,e = p.communicate()
                if p.returncode == 0 and not "up to date" in o.decode("utf-8"):
                    updated = True
            except:
                pass
            os.chdir(cwd)
            if updated:
                lines = print_line(lines," - Updated, restarting...\n")
                # Restart ourselves via subprocess
                p = subprocess.Popen([sys.executable,os.path.realpath(__file__)]+sys.argv[1:])
                try:
                    p.communicate()
                except KeyboardInterrupt:
                    exit()
                exit(p.returncode)
            lines = print_line(lines," - Already up to date\n")
    # Gather info as needed - first check for java
    if not JAVA_PATH:
        print("Could not locate java!")
        print("")
        exit(1)
    # Let's verify if we have an application.yml or not - and inform the user
    if not os.path.isfile(YML_PATH):
        print("{} not found!\n".format(YML_PATH))
        print("Please visit the following link to create one:")
        print(" - {}\n".format(DOC_URL))
        exit(1)
    # Scrape the Lavalink and YouTube-Source versions
    lines = print_line(lines,"Local versions:")
    ll_version = check_lavalink_version(LAVALINK_PATH)
    lines = print_line(lines," - Lavalink: {}".format(ll_version or "MISSING"))
    yts_version = check_yts_version(YML_PATH)
    plugin_dir = check_plugin_dir(YML_PATH)
    if not plugin_dir:
        print("Could not locate a valid pluginsDir in {}!\n".format(YML_PATH))
        print("Please ")
    yts_path = os.path.join(plugin_dir,"youtube-plugin-{}.jar".format(yts_version))
    lines = print_line(lines," - YouTube-Source: {}{}".format(
        yts_version or "MISSING",
        " - PLUGIN FOLDER MISSING" if not os.path.isdir(plugin_dir) \
        else " - FILE MISSING" if not os.path.isfile(yts_path) else ""
    ))
    if not yts_version:
        print("\nCould not locate youtube-plugin information in")
        print(" - {}".format(YML_PATH))
        print("")
        print("Please visit the following link for info:")
        print(" - {}\n".format(DOC_URL))
        exit(1)
    # The GitHub API expects api.github.com/repos/OWNER/REPO/releases/tags/TAG
    # if not latest
    y_api_target = l_api_target = None
    if l_target:
        l_target = quote(l_target)
        l_api_target = "tags/{}".format(l_target)
    if y_target:
        y_target = quote(y_target)
        y_api_target = "tags/{}".format(y_target)
    # If we're only forcing when different - check if they're not equal,
    # otherwise check for remote > local
    allowed_comparisons = (True,False) if force_if_different else (True,)
    lines = print_line(lines,"Remote versions:")
    l_success,l_version,l_url = get_latest_info(
        LAVALINK_URL.format(l_target or "latest"),
        LAVALINK_API.format(l_api_target or "latest"),
        LAVALINK_REG,
        prioritize_html=prioritize_html
    )
    if not l_success:
        lines = print_line(lines," - Lavalink: Error checking for updates")
    else:
        lines = print_line(lines," - Lavalink: {}".format(l_version))
    y_success,y_version,y_url = get_latest_info(
        YTSOURCE_URL.format(y_target or "latest"),
        YTSOURCE_API.format(y_api_target or "latest"),
        YTSOURCE_REG,
        prioritize_html=prioritize_html
    )
    if not y_success:
        lines = print_line(lines," - YouTube-Source: Error checking for updates")
    else:
        lines = print_line(lines," - YouTube-Source: {}".format(y_version))
    if list_update:
        # Print if either needs an update
        if y_version or l_version:
            lines = print_line(lines,"")
        if l_version:
            if ll_version is None or u.compare_versions(ll_version,l_version):
                lines = print_line(lines,"Lavalink update available")
            else:
                lines = print_line(lines,"Lavalink is up to date")
        if y_version:
            if yts_version is None or u.compare_versions(yts_version,y_version):
                lines = print_line(lines,"YouTube-Source update available")
            else:
                lines = print_line(lines,"YouTube-Source is up to date")
        exit()
    # Updates are required if the current file does not exist, if we're
    # forcing updates, or if our version number means we need one
    #
    files_to_update = []
    # Let's see if we qualify for updates
    l_allowed = force or ll_version  is None or ((only_update or update) and u.compare_versions(ll_version,l_version)  in allowed_comparisons)
    y_allowed = force or yts_version is None or ((only_update or update) and u.compare_versions(yts_version,y_version) in allowed_comparisons)
    # First we check if Lavalink needs to be updated - and download it to a temp dir
    temp = None
    if l_allowed:
        lines = print_line(lines,"\n{}Updating Lavalink...".format("Force-" if force or force_if_different else ""))
        if not any((l_url,l_version)):
            lines = print_line(lines," - Could not resolve URL or version!  Skipping...")
        else:
            lines = print_line(lines,"")
            lines = print_line(lines,"Downloading {} ({})...".format(os.path.basename(l_url),l_version))
            temp = temp or tempfile.mkdtemp()
            try:
                ll_temp = DL.stream_to_file(l_url,os.path.join(temp,os.path.basename(l_url)))
                assert ll_temp is not None
                # Add it to the list of files to update
                files_to_update.append((
                    ll_temp,
                    LAVALINK_PATH,
                    l_version
                ))
            except Exception as e:
                lines = print_line(lines," - Failed to download: {}".format(e))
    if y_allowed or not os.path.isfile(yts_path):
        lines = print_line(lines,"\n{}Updating YouTube-Source...".format("Force-" if force or force_if_different else ""))
        if not y_allowed and yts_version:
            # We're not explicitly updating, but our declared
            # file does not exist.  Let's override the search
            # values with the one we're expecting.
            y_target = quote(yts_version)
            y_api_target = "tags/{}".format(y_target)
            y_success,y_version,y_url = get_latest_info(
                YTSOURCE_URL.format(y_target or "latest"),
                YTSOURCE_API.format(y_api_target or "latest"),
                YTSOURCE_REG,
                prioritize_html=prioritize_html
            )
        if not any((y_url,y_version)):
            lines = print_line(lines," - Could not resolve URL or version!  Skipping...")
        else:
            lines = print_line(lines,"")
            lines = print_line(lines,"Downloading {} ({})...".format(os.path.basename(y_url),y_version))
            temp = temp or tempfile.mkdtemp()
            try:
                yt_temp = DL.stream_to_file(y_url,os.path.join(temp,os.path.basename(y_url)))
                assert yt_temp is not None
                # Update the yml to expect the new version
                yml_temp = update_yts_version(YML_PATH,y_version,temp)
                assert yml_temp is not None
                # Add both to the list of files to update
                files_to_update.extend([
                    (
                        yt_temp,
                        os.path.join(plugin_dir,os.path.basename(yt_temp)),
                        y_version
                    ),
                    (
                        yml_temp,
                        YML_PATH,
                        y_version
                    )
                ])
            except Exception as e:
                lines = print_line(lines," - Failed to download: {}".format(e))
    if files_to_update:
        # Iterate the files we need to update
        lines = print_line(lines,"\nMoving files into place...")
        # Prompt to quit other instances - even if just updating
        prompt_answer,printed = check_pids(prompt_answer=prompt_answer,temp=temp)
        if printed:
            # Re-print our prior lines
            u.head()
            print("\n".join(lines))
        for src,dest,vers in files_to_update:
            lines = print_line(lines," - {}{}".format(
                os.path.basename(src),
                " ({})".format(vers) if vers else ""
            ))
            try:
                if not os.path.isdir(os.path.dirname(dest)):
                    # Attempt to create missing directories
                    os.makedirs(os.path.dirname(dest))
                # Copy the target file
                shutil.move(src,dest)
            except Exception as e:
                lines = print_line(lines," --> Failed to copy: {}".format(e))
    # Clean up the temp directory, if any
    cleanup(temp)
    if only_update:
        # Bail here if we're only updating
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
        exit(1)
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
    try:
        exit(lavalink.returncode)
    except:
        # We couldn't get the return code - the process
        # was likely killed - so exit with a 0 status
        exit(0)

JAVA_PATH = get_bin_path("java")
USE_WMIC = get_bin_path("wmic")
if os.name == "nt":
    if USE_WMIC:
        COMMAND_REG = re.compile(r"(?i)^(?P<command>.*)\s+(?P<pid>\d+).*$")
    else:
        COMMAND_REG = re.compile(r"(?i)^\s*(?P<pid>\d+)\s+(?P<command>.*)$")
else:
    COMMAND_REG = re.compile(r"(?i)^([^\s]+\s+)(?P<pid>\d+)\s+([^\s]+\s+){8}(?P<command>.*)$")

if __name__ == "__main__":
    # Setup the cli args
    parser = argparse.ArgumentParser(prog="Lavalink.py", description="Lavalink.py - a py script to update and launch Lavalink.jar")
    parser.add_argument("-c", "--check-updates", help="only report the latest Lavalink and YouTube-Source versions (implies --skip-git, overrides all but --help)", action="store_true")
    parser.add_argument("-l", "--lavalink-version", help="update Lavalink.jar to the passed version tag instead of \"latest\" if it exists (requires --force[-if-different] if passing an older version)")
    parser.add_argument("-y", "--yts-version", help="update YouTube-Source to the passed version tag instead of \"latest\" if it exists (requires --force[-if-different] if passing an older version)")
    parser.add_argument("-f", "--force", help="force Lavalink.jar and YouTube-Source updates (overrides --force-if-different)", action="store_true")
    parser.add_argument("-d", "--force-if-different", help="force Lavalink.jar and YouTube-Source updates only if the local and remote versions are different", action="store_true")
    parser.add_argument("-s", "--skip-updates", help="skip update checks (overrides --force)", action="store_true")
    parser.add_argument("-o", "--only-update", help="only update, don't start Lavalink (overrides --skip-updates)", action="store_true")
    parser.add_argument("-g", "--skip-git", help="GitHub self updates", action="store_true")
    parser.add_argument("-p", "--prioritize-html", help="attempt to scrape html for updates before falling back on the GitHub JSON API (by default, the API is checked first)", action="store_true")
    parser.add_argument("-r", "--handle-running", help="how to handle detected currently running Lavalink.jar instances", choices=["kill","ignore","quit","ask"], default="ask")

    args = parser.parse_args()

    prompt_dict = {"kill":"y","ignore":"n","quit":"q"}
    main(
        skip_git=args.skip_git,
        list_update=args.check_updates,
        update=not args.skip_updates,
        only_update=args.only_update,
        prioritize_html=args.prioritize_html,
        force=args.force,
        force_if_different=args.force_if_different,
        prompt_answer=prompt_dict.get(args.handle_running),
        l_target=args.lavalink_version,
        y_target=args.yts_version
    )
