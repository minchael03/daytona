"""Native accessibility checks: alt text, contrast, form labels, button names, font size.

Pure functions and a synchronous Playwright scan. No file writes, no HTTP,
no model API calls. See AGENTS.md contract 1 for the interface this module
must expose to worker/UI callers.
"""

FONT_SIZE_MIN_PX = 16
LARGE_TEXT_MIN_PX = 24
LARGE_TEXT_BOLD_MIN_PX = 18.667
LARGE_TEXT_BOLD_MIN_WEIGHT = 700
NORMAL_TEXT_THRESHOLD = 4.5
LARGE_TEXT_THRESHOLD = 3.0

_COLLECT_JS = r"""
() => {
  function parseColor(value) {
    if (!value) return null;
    const m = value.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const parts = m[1].split(',').map(s => parseFloat(s.trim()));
    const [r, g, b, a] = parts;
    return { r, g, b, a: a === undefined ? 1 : a };
  }

  function accessibleNameParts(el) {
    const ariaLabel = el.getAttribute('aria-label');
    const ariaLabelledby = el.getAttribute('aria-labelledby');
    let labelledbyText = null;
    if (ariaLabelledby) {
      const texts = ariaLabelledby.split(/\s+/).map(id => {
        const ref = document.getElementById(id);
        return ref ? ref.textContent.trim() : '';
      }).filter(Boolean);
      labelledbyText = texts.length ? texts.join(' ') : null;
    }
    return {
      ariaLabel: ariaLabel && ariaLabel.trim() ? ariaLabel.trim() : null,
      ariaLabelledbyText: labelledbyText,
      title: el.getAttribute('title'),
      textContent: el.textContent ? el.textContent.trim() : '',
    };
  }

  function isRendered(el) {
    const style = getComputedStyle(el);
    return style.display !== 'none' && style.visibility !== 'hidden';
  }

  function selectorFor(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    const path = [];
    let node = el;
    while (node && node.nodeType === 1 && path.length < 6) {
      let part = node.tagName.toLowerCase();
      if (node.classList.length) part += '.' + Array.from(node.classList).map(c => CSS.escape(c)).join('.');
      const parent = node.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(c => c.tagName === node.tagName);
        if (siblings.length > 1) part += ':nth-of-type(' + (siblings.indexOf(node) + 1) + ')';
      }
      path.unshift(part);
      node = node.parentElement;
    }
    return path.join(' > ');
  }

  function resolveBackground(el) {
    let node = el;
    while (node) {
      const style = getComputedStyle(node);
      if (style.backgroundImage && style.backgroundImage !== 'none') return { unresolvable: true };
      if (style.filter && style.filter !== 'none') return { unresolvable: true };
      if (style.mixBlendMode && style.mixBlendMode !== 'normal') return { unresolvable: true };
      const opacity = parseFloat(style.opacity);
      if (!isNaN(opacity) && opacity < 1) return { unresolvable: true };
      const bg = parseColor(style.backgroundColor);
      if (bg) {
        if (bg.a === 1) return { unresolvable: false, rgb: [bg.r, bg.g, bg.b] };
        if (bg.a > 0) return { unresolvable: true };
      }
      node = node.parentElement;
    }
    return { unresolvable: true };
  }

  function textInfo(el) {
    const style = getComputedStyle(el);
    const fontSizePx = parseFloat(style.fontSize);
    const fontWeight = parseInt(style.fontWeight, 10) || 400;
    const unresolvable = () => ({ unresolvable: true, fontSizePx, fontWeight });
    if (style.textShadow && style.textShadow !== 'none') return unresolvable();
    if (style.transform && style.transform !== 'none') return unresolvable();
    const fg = parseColor(style.color);
    if (!fg || fg.a < 1) return unresolvable();
    const bg = resolveBackground(el);
    if (bg.unresolvable) return unresolvable();
    return {
      unresolvable: false,
      fg: [fg.r, fg.g, fg.b],
      bg: bg.rgb,
      fontSizePx,
      fontWeight,
    };
  }

  const results = { images: [], formControls: [], buttons: [], textNodes: [] };

  document.querySelectorAll('img').forEach(img => {
    if (!isRendered(img)) return;
    const hasAlt = img.hasAttribute('alt');
    const alt = hasAlt ? img.getAttribute('alt').trim() : null;
    const name = accessibleNameParts(img);
    results.images.push({
      selector: selectorFor(img),
      hasAlt,
      alt,
      ariaLabel: name.ariaLabel,
      ariaLabelledbyText: name.ariaLabelledbyText,
      title: name.title,
    });
  });

  document.querySelectorAll('input, select, textarea').forEach(control => {
    const type = (control.getAttribute('type') || '').toLowerCase();
    if (type === 'hidden') return;
    if (type === 'button' || type === 'submit' || type === 'reset' || type === 'image') return;
    if (!isRendered(control)) return;
    let labelText = null;
    if (control.id) {
      const label = document.querySelector('label[for="' + CSS.escape(control.id) + '"]');
      if (label) labelText = label.textContent.trim();
    }
    if (!labelText) {
      const wrapping = control.closest('label');
      if (wrapping) labelText = wrapping.textContent.trim();
    }
    const name = accessibleNameParts(control);
    results.formControls.push({
      selector: selectorFor(control),
      labelText: labelText || null,
      ariaLabel: name.ariaLabel,
      ariaLabelledbyText: name.ariaLabelledbyText,
      title: name.title,
      placeholder: control.getAttribute('placeholder'),
    });
  });

  function buttonNameInfo(el) {
    const name = accessibleNameParts(el);
    const imgWithAlt = el.querySelector('img[alt]');
    const imgAlt = imgWithAlt ? imgWithAlt.getAttribute('alt').trim() : null;
    const value = el.tagName === 'INPUT' ? el.getAttribute('value') : null;
    return {
      ariaLabel: name.ariaLabel,
      ariaLabelledbyText: name.ariaLabelledbyText,
      title: name.title && name.title.trim() ? name.title.trim() : null,
      textContent: name.textContent,
      imgAlt: imgAlt && imgAlt.length ? imgAlt : null,
      value: value && value.trim() ? value.trim() : null,
    };
  }

  document.querySelectorAll('button').forEach(btn => {
    if (!isRendered(btn)) return;
    results.buttons.push(Object.assign({ selector: selectorFor(btn) }, buttonNameInfo(btn)));
  });
  document.querySelectorAll('input[type="button" i], input[type="submit" i], input[type="reset" i]').forEach(btn => {
    if (!isRendered(btn)) return;
    results.buttons.push(Object.assign({ selector: selectorFor(btn) }, buttonNameInfo(btn)));
  });

  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
  const seen = new Set();
  let node = walker.currentNode;
  while (node) {
    if (node.nodeType === 1) {
      const hasDirectText = Array.from(node.childNodes).some(
        c => c.nodeType === 3 && c.textContent.trim().length > 0
      );
      if (hasDirectText && isRendered(node) && !seen.has(node)) {
        seen.add(node);
        const info = textInfo(node);
        if (info.unresolvable) {
          results.textNodes.push({
            selector: selectorFor(node),
            unresolvable: true,
            fontSizePx: info.fontSizePx,
            fontWeight: info.fontWeight,
          });
        } else {
          results.textNodes.push({
            selector: selectorFor(node),
            unresolvable: false,
            fg: info.fg,
            bg: info.bg,
            fontSizePx: info.fontSizePx,
            fontWeight: info.fontWeight,
          });
        }
      }
    }
    node = walker.nextNode();
  }

  return results;
}
"""


def _srgb_channel_to_linear(channel_255):
    channel = channel_255 / 255
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(rgb):
    r, g, b = rgb
    return (
        0.2126 * _srgb_channel_to_linear(r)
        + 0.7152 * _srgb_channel_to_linear(g)
        + 0.0722 * _srgb_channel_to_linear(b)
    )


def contrast_ratio(rgb_a, rgb_b):
    luminance_a = _relative_luminance(rgb_a)
    luminance_b = _relative_luminance(rgb_b)
    lighter = max(luminance_a, luminance_b)
    darker = min(luminance_a, luminance_b)
    return (lighter + 0.05) / (darker + 0.05)


def required_contrast(font_size, weight):
    is_large = font_size >= LARGE_TEXT_MIN_PX or (
        weight >= LARGE_TEXT_BOLD_MIN_WEIGHT and font_size >= LARGE_TEXT_BOLD_MIN_PX
    )
    return LARGE_TEXT_THRESHOLD if is_large else NORMAL_TEXT_THRESHOLD


def meets_contrast(ratio, threshold):
    return ratio >= threshold


def _image_alt_findings(images):
    findings = []
    for img in images:
        target = img["selector"]
        if img["ariaLabel"] or img["ariaLabelledbyText"]:
            status, summary = "pass", "유효한 ARIA 이름이 있습니다."
        elif img["hasAlt"] and img["alt"]:
            status, summary = "pass", "대체 텍스트가 있습니다."
        elif img["hasAlt"] and img["alt"] == "":
            status, summary = "needs_review", "빈 alt는 장식 의도인지 확인이 필요합니다."
        elif img["title"]:
            status, summary = "needs_review", "title만 있어 이름 근거가 불확실합니다."
        else:
            status, summary = "fail", "대체 텍스트와 이름 근거가 없습니다."
        findings.append({
            "rule_id": "image_alt",
            "status": status,
            "target": target,
            "summary": summary,
            "evidence": {
                "has_alt": img["hasAlt"],
                "alt": img["alt"],
                "aria_label": img["ariaLabel"],
                "aria_labelledby_text": img["ariaLabelledbyText"],
                "title": img["title"],
            },
            "basis": "basic-presence",
        })
    return findings


def _form_label_findings(controls):
    findings = []
    for control in controls:
        target = control["selector"]
        if control["labelText"] or control["ariaLabel"] or control["ariaLabelledbyText"]:
            status, summary = "pass", "연결된 이름 근거가 있습니다."
        elif control["title"]:
            status, summary = "needs_review", "title만 있어 이름 근거가 불확실합니다."
        else:
            status, summary = "fail", "연결된 레이블이나 이름 근거가 없습니다."
        findings.append({
            "rule_id": "form_label",
            "status": status,
            "target": target,
            "summary": summary,
            "evidence": {
                "label_text": control["labelText"],
                "aria_label": control["ariaLabel"],
                "aria_labelledby_text": control["ariaLabelledbyText"],
                "title": control["title"],
                "placeholder": control["placeholder"],
            },
            "basis": "basic-presence",
        })
    return findings


def _button_name_findings(buttons):
    findings = []
    for btn in buttons:
        target = btn["selector"]
        name = (
            btn["ariaLabel"]
            or btn["ariaLabelledbyText"]
            or (btn["textContent"] if btn["textContent"] else None)
            or btn["imgAlt"]
            or btn["title"]
            or btn["value"]
        )
        if name:
            status, summary = "pass", "접근 가능한 이름이 있습니다."
        else:
            status, summary = "fail", "접근 가능한 이름이 없습니다."
        findings.append({
            "rule_id": "button_name",
            "status": status,
            "target": target,
            "summary": summary,
            "evidence": {
                "aria_label": btn["ariaLabel"],
                "aria_labelledby_text": btn["ariaLabelledbyText"],
                "text_content": btn["textContent"],
                "img_alt": btn["imgAlt"],
                "title": btn["title"],
                "value": btn["value"],
            },
            "basis": "basic-presence",
        })
    return findings


def _contrast_and_font_findings(text_nodes):
    findings = []
    for node in text_nodes:
        target = node["selector"]
        if node["unresolvable"]:
            findings.append({
                "rule_id": "contrast",
                "status": "needs_review",
                "target": target,
                "summary": "단순 계산으로 확정할 수 없는 배경/전경입니다.",
                "evidence": {},
                "basis": "wcag-1.4.3",
            })
        else:
            ratio = contrast_ratio(tuple(node["fg"]), tuple(node["bg"]))
            threshold = required_contrast(node["fontSizePx"], node["fontWeight"])
            passes = meets_contrast(ratio, threshold)
            findings.append({
                "rule_id": "contrast",
                "status": "pass" if passes else "fail",
                "target": target,
                "summary": "명도 대비를 충족합니다." if passes else "명도 대비가 기준에 못 미칩니다.",
                "evidence": {
                    "fg": node["fg"],
                    "bg": node["bg"],
                    "font_size_px": node["fontSizePx"],
                    "font_weight": node["fontWeight"],
                    "ratio": ratio,
                    "required_ratio": threshold,
                },
                "basis": "wcag-1.4.3",
            })

        if node["fontSizePx"] < FONT_SIZE_MIN_PX:
            findings.append({
                "rule_id": "font_size",
                "status": "needs_review",
                "target": target,
                "summary": "글자가 제품 권장값보다 작습니다.",
                "evidence": {
                    "font_size_px": node["fontSizePx"],
                    "recommended_min_px": FONT_SIZE_MIN_PX,
                },
                "basis": "product-guidance",
            })
    return findings


def inspect_snapshot(snapshot):
    findings = []
    findings.extend(_image_alt_findings(snapshot.get("images", [])))
    findings.extend(_form_label_findings(snapshot.get("formControls", [])))
    findings.extend(_button_name_findings(snapshot.get("buttons", [])))
    findings.extend(_contrast_and_font_findings(snapshot.get("textNodes", [])))
    return findings


def scan(page):
    snapshot = page.evaluate(_COLLECT_JS)
    findings = inspect_snapshot(snapshot)
    return {"snapshot": snapshot, "findings": findings}
