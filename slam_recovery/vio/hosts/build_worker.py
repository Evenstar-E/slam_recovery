"""Link a replay adapter against an already-built pinned VINS-Fusion or OKVIS2 host."""
import argparse
from pathlib import Path
import shlex
import subprocess


def build_vins(build, vins_source, dependency_dirs, source, output):
    target = build / "CMakeFiles/vins_node.dir"
    flags = dict(line.split(" = ", 1) for line in (target / "flags.make").read_text().splitlines()
                 if line.startswith(("CXX_DEFINES = ", "CXX_INCLUDES = ")))
    obj = output.with_suffix(".o")
    compile_flags = shlex.split(flags["CXX_DEFINES"]) + shlex.split(flags["CXX_INCLUDES"])
    subprocess.run(["/usr/bin/c++", "-std=c++11", "-O1", *compile_flags, f"-I{vins_source}",
                    "-c", str(source), "-o", str(obj)], cwd=build, check=True)
    link = shlex.split((target / "link.txt").read_text())
    link[link.index("-o") + 1] = str(output)
    host_object = next(index for index, arg in enumerate(link) if arg.endswith("rosNodeTest.cpp.o"))
    link[host_object] = str(obj)
    link.extend(("-ldl", "-Wl,--export-dynamic"))
    link.extend(f"-Wl,-rpath-link,{directory}" for directory in dependency_dirs)
    subprocess.run(link, cwd=build, check=True)


def build_okvis(build, source, output):
    lines = subprocess.check_output(
        ["ninja", "-t", "commands", "okvis_app_synchronous"], cwd=build, text=True).splitlines()
    compile = next(shlex.split(line) for line in lines if " -c " in line
                   and line.endswith("/okvis_apps/src/okvis_app_synchronous.cpp"))
    obj = output.with_suffix(".o")
    native_obj = compile[compile.index("-o") + 1]
    paths = {native_obj: str(obj), native_obj + ".d": str(obj) + ".d", "-O3": "-O1"}
    compile[-1] = str(source)
    subprocess.run([paths.get(arg, arg) for arg in compile], cwd=build, check=True)

    # Ninja emits the link command between two no-op commands from CMake.
    link_line = lines[-1].split(" && ")[1]
    link = shlex.split(link_line)
    link[link.index(native_obj)] = str(obj)
    link[link.index("-o") + 1] = str(output)
    subprocess.run(link, cwd=build, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=("vins", "okvis"))
    parser.add_argument("host_build", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--vins-source", type=Path,
                        help="VINS-Fusion/vins_estimator/src directory")
    parser.add_argument("--link-dependency", type=Path, action="append", default=[])
    args = parser.parse_args()
    source = Path(__file__).resolve().parent / f"{args.host}_worker.cc"
    build = args.host_build.resolve(strict=True)
    output = args.output.resolve()
    if args.host == "vins":
        if args.vins_source is None:
            parser.error("--vins-source is required for VINS-Fusion")
        build_vins(build, args.vins_source.resolve(strict=True),
                   [path.resolve(strict=True) for path in args.link_dependency], source, output)
    else:
        build_okvis(build, source, output)


if __name__ == "__main__":
    main()
