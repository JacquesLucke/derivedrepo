import subprocess
from derivedrepo import DerivedGitRepo

def build(source_path):
    subprocess.run(["python", "setup.py", "build", "--noversioncheck"], cwd=source_path)
    return source_path / "animation_nodes"

repo = DerivedGitRepo(
    "/home/jacques/Desktop/animation_nodes",
    "/home/jacques/Desktop/derivedrepo/local_stuff",
    "/home/jacques/Desktop/derivedrepo/remote_config.json",
    build,
    checkout_dir="/home/jacques/.config/blender/2.80/scripts/addons/animation_nodes")

#repo.checkout("66cbdd8eb46ef1e2f7ab3bb2013f7f272ff66fb9")
repo.add_last_n("blender2.8", 10)