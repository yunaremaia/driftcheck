"""Jenkins drift detection: Jenkinsfile tool versions vs README."""
from __future__ import annotations
import re

# Match tool version declarations in Jenkinsfile
# e.g., node('20'), nodejs '20', python '3.11', docker.image('node:20')
JENKINS_NODE_RE = re.compile(r"""node\s*\(\s*['"](?P<agent>[^'"]+)['"]\s*\)""", re.I)
JENKINS_NODEJS_RE = re.compile(r"""nodejs\s+['"](?P<version>[\d.]+)['"]""", re.I)
JENKINS_PYTHON_RE = re.compile(r"""python\s+['"](?P<version>[\d.]+)['"]""", re.I)
JENKINS_DOCKER_IMAGE_RE = re.compile(r"""docker\.image\s*\(\s*['"](?P<image>[\w.\-/]+):(?P<tag>[\w.\-]+)['"]\s*\)""", re.I)
JENKINS_SH_VERSION_RE = re.compile(r"""sh\s+['"](?P<cmd>[^'"]*(?:node|python|go|rust|java|dotnet|npm|yarn|pip)[^'"]*)['"]""", re.I)

# Match version mentions in README
JENKINS_VER_RE = re.compile(
    r'(?:node\.js|nodejs|node|python|go|rust|java|dotnet|npm|yarn|pip)\s*[:=]?\s*(?P<version>[\d.]+)',
    re.I,
)


def parse_jenkins_node_agent(text: str) -> str | None:
    """Return the agent label from node() declaration."""
    m = JENKINS_NODE_RE.search(text)
    return m.group("agent") if m else None


def parse_jenkins_nodejs_version(text: str) -> str | None:
    """Return the Node.js version from nodejs tool declaration."""
    m = JENKINS_NODEJS_RE.search(text)
    return m.group("version") if m else None


def parse_jenkins_python_version(text: str) -> str | None:
    """Return the Python version from python tool declaration."""
    m = JENKINS_PYTHON_RE.search(text)
    return m.group("version") if m else None


def parse_jenkins_docker_images(text: str) -> dict[str, str]:
    """Return {image: tag} map of docker images in Jenkinsfile."""
    result = {}
    for m in JENKINS_DOCKER_IMAGE_RE.finditer(text):
        result[m.group("image")] = m.group("tag")
    return result


def find_jenkins_drift(jenkins_files: dict[str, str], docs: dict[str, str]) -> list[dict]:
    """Detect drift between Jenkinsfile tool versions and README mentions."""
    all_nodejs: dict[str, str] = {}
    all_python: dict[str, str] = {}
    all_docker: dict[str, str] = {}
    all_agents: dict[str, str] = {}

    for fname, content in jenkins_files.items():
        node_agent = parse_jenkins_node_agent(content)
        if node_agent:
            all_agents[fname] = node_agent
        nodejs_ver = parse_jenkins_nodejs_version(content)
        if nodejs_ver:
            all_nodejs[fname] = nodejs_ver
        python_ver = parse_jenkins_python_version(content)
        if python_ver:
            all_python[fname] = python_ver
        for img, tag in parse_jenkins_docker_images(content).items():
            all_docker[img] = tag

    if not all_nodejs and not all_python and not all_docker and not all_agents:
        return []

    drifts = []

    # Check Node.js version drift
    for fname, nodejs_ver in all_nodejs.items():
        for doc_fname, doc_content in docs.items():
            for m in JENKINS_VER_RE.finditer(doc_content):
                tool = m.group(0).split()[0].lower()
                if "node" in tool or "nodejs" in tool:
                    doc_ver = m.group("version")
                    if not _versions_match(doc_ver, nodejs_ver):
                        drifts.append({
                            "file": doc_fname,
                            "tool": "Node.js",
                            "doc_version": doc_ver,
                            "jenkins_version": nodejs_ver,
                            "pos": m.start(),
                        })
                        break
            break  # one per file

    # Check Python version drift
    for fname, python_ver in all_python.items():
        for doc_fname, doc_content in docs.items():
            for m in JENKINS_VER_RE.finditer(doc_content):
                tool = m.group(0).split()[0].lower()
                if "python" in tool:
                    doc_ver = m.group("version")
                    if not _versions_match(doc_ver, python_ver):
                        drifts.append({
                            "file": doc_fname,
                            "tool": "Python",
                            "doc_version": doc_ver,
                            "jenkins_version": python_ver,
                            "pos": m.start(),
                        })
                        break
            break

    # Check Docker image drift
    for img, tag in all_docker.items():
        for doc_fname, doc_content in docs.items():
            for m in JENKINS_VER_RE.finditer(doc_content):
                doc_ver = m.group("version")
                if img.lower() in m.group(0).lower():
                    if not _versions_match(doc_ver, tag):
                        drifts.append({
                            "file": doc_fname,
                            "tool": f"Docker ({img})",
                            "doc_version": doc_ver,
                            "jenkins_version": tag,
                            "pos": m.start(),
                        })
                        break
            break

    return drifts


def _versions_match(doc_ver: str, jenkins_ver: str) -> bool:
    """Return True when versions are equivalent (handles '20' vs '20.0')."""
    if doc_ver == jenkins_ver:
        return True
    # Handle major-only vs major.minor
    if jenkins_ver.startswith(doc_ver + "."):
        return True
    if doc_ver.startswith(jenkins_ver + "."):
        return True
    # Handle major.minor vs major.minor.patch
    doc_parts = doc_ver.split(".")
    jenkins_parts = jenkins_ver.split(".")
    if len(doc_parts) >= 2 and len(jenkins_parts) >= 2:
        return doc_parts[0] == jenkins_parts[0] and doc_parts[1] == jenkins_parts[1]
    return False
