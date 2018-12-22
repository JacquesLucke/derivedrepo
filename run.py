import time
import subprocess
from derivedrepo import DerivedGitRepo

def build(source_path):
    start = time.perf_counter()
    subprocess.run(["python", "setup.py", "build", "--noversioncheck"], cwd=source_path)
    end = time.perf_counter()
    return source_path / "animation_nodes", {"buildTime":(end - start)}

repo = DerivedGitRepo(
    "/home/jacques/Desktop/animation_nodes",
    "/home/jacques/Desktop/derivedrepo/local_stuff",
    build)

repo.checkout("a6db09876c184e343ec2821de45c3dd25cfe4d23")
#repo.add_last_days("blender2.8", 10)
#repo.add_last_n("blender2.8", 20)
#repo.add_remote_file_repo_group("/home/jacques/Documents/remote_test")
#repo.upload_all()

#repo.checkout("66cbdd8eb46ef1e2f7ab3bb2013f7f272ff66fb9")
#repo.add_last_n("blender2.8", 10)