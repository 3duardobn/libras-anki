import os
import xml.etree.ElementTree as ET

def get_output_dir(pasta_name):
    """
    Retorna o caminho absoluto do diretório de saída correspondente.
    Se o caminho for relativo (ex: 'animais'), resolve-o sob a pasta raiz 'output/'.
    Se já for absoluto ou começar com 'output', preserva o caminho original.
    """
    if not pasta_name:
        return os.path.abspath("output")
    if os.path.isabs(pasta_name):
        return pasta_name
    
    norm = os.path.normpath(pasta_name)
    parts = norm.split(os.sep)
    if parts[0] == "output":
        return os.path.abspath(norm)
        
    return os.path.abspath(os.path.join("output", norm))


def sanitize_svg_for_qt(content: bytes | str) -> bytes:
    """
    Sanitiza SVGs de SignWriting (ex: SignPuddle) para compatibilidade com Qt (SVG Tiny 1.2).
    Converte elementos aninhados <svg x='...' y='...'> em <g transform='translate(...)'>
    e remove tags <text font-size='0'> que geram warnings ou quebram o renderizador do Qt.
    """
    if not content:
        return b""
    try:
        xml_str = content.decode("utf-8") if isinstance(content, bytes) else content
        SVG_NS = "http://www.w3.org/2000/svg"
        ET.register_namespace("", SVG_NS)
        root = ET.fromstring(xml_str)

        def process_element(elem):
            for child in list(elem):
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if tag == "text" and child.attrib.get("font-size") in ("0", "0px"):
                    elem.remove(child)
                    continue
                elif tag == "svg":
                    child.tag = f"{{{SVG_NS}}}g"
                    x = child.attrib.pop("x", "0")
                    y = child.attrib.pop("y", "0")
                    existing_transform = child.attrib.get("transform", "")
                    trans = f"translate({x}, {y})"
                    if existing_transform:
                        child.attrib["transform"] = f"{trans} {existing_transform}"
                    else:
                        child.attrib["transform"] = trans
                process_element(child)

        process_element(root)
        return ET.tostring(root, encoding="utf-8")
    except Exception:
        return content if isinstance(content, bytes) else content.encode("utf-8")

