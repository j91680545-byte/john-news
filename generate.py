#!/usr/bin/env python3
"""
John News generator.
Fetches current HN front page, asks Claude to write a custom John-ification
for every headline, then writes index.html.
"""

import re
import json
import html as html_module
import urllib.request
import sys
import os


# ---------------------------------------------------------------------------
# Fallback suffixes — used if the Claude API is unavailable
# ---------------------------------------------------------------------------
FALLBACK_SUFFIXES = [
    "John Already Knew This",
    "John Predicted This Last Year",
    "John's Version Is Better",
    "John Wrote a Better Implementation Over the Weekend",
    "John Called This Three Years Ago",
    "John's PR Review Improved It by 40%",
    "John Was Not Surprised",
    "John Had Already Solved This",
    "John's Fork Has Twice the Stars",
    "John Reviewed This and Found Three More Issues",
    "John's Explanation Remains the Clearest Ever Written",
    "John Prototyped This Last Quarter",
    "John Had Been Saying This for Years",
    "Nobody Told John, He Just Knew",
    "John's Implementation Uses 40% Less Memory",
    "John Suggested This in a Slack Message Two Years Ago",
    "John Peer-Reviewed This and Improved the Algorithm",
    "John Benchmarked This Against Himself and Won",
    "John Closed a Related PR Before Breakfast",
    "John Nodded Approvingly Upon Reading This",
]

def fallback_john_ify(title, idx):
    suffix = FALLBACK_SUFFIXES[idx % len(FALLBACK_SUFFIXES)]
    return f"{title.rstrip('.!?')}, {suffix}"


# ---------------------------------------------------------------------------
# Claude-powered John-ification — one API call for the whole batch
# ---------------------------------------------------------------------------
def claude_john_ify(titles):
    """
    Send all headlines to Claude in one call.
    Returns a list of John-ified headlines in the same order.
    Falls back to suffix approach on any error.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("  No ANTHROPIC_API_KEY found, using fallback suffixes.")
        return None

    try:
        import anthropic
    except ImportError:
        print("  anthropic package not installed, using fallback suffixes.")
        return None

    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(titles))

    prompt = f"""You are writing headlines for "John News" — a parody of Hacker News where every story is about how brilliant, talented, and ahead-of-the-curve John is.

Here are today's real Hacker News headlines. Rewrite each one to include a funny, specific reference to John being great. Rules:
- Keep the core topic of the original headline intact so readers recognise it
- Make the John reference feel earned and specific to THAT story, not generic
- Vary the structure: sometimes John leads the headline, sometimes he appears at the end, sometimes mid-sentence
- Be concise — HN headline length
- No em dashes. Use commas, colons, or new sentences instead
- Be funny. Dry wit works best
- Return ONLY a JSON array of strings, one per headline, in the same order. No markdown, no explanation.

Headlines:
{numbered}"""

    client = anthropic.Anthropic(api_key=api_key)
    try:
        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        result = json.loads(raw)
        if isinstance(result, list) and len(result) == len(titles):
            return result
        print(f"  Unexpected response shape, falling back.")
        return None
    except Exception as e:
        print(f"  Claude API error: {e}, using fallback suffixes.")
        return None


# ---------------------------------------------------------------------------
# Fetch + parse HN front page
# ---------------------------------------------------------------------------
def fetch_hn_stories():
    import ssl
    # On macOS the system Python may lack bundled CA certs; fall back gracefully
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        "https://news.ycombinator.com/news",
        headers={"User-Agent": "Mozilla/5.0 (compatible; JohnNewsBot/1.0)"},
    )
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        content = resp.read().decode("utf-8", errors="replace")

    # Parse titleline entries
    titles_urls = re.findall(
        r'class="titleline"><a href="([^"]+)">(.+?)</a>', content
    )

    # Parse item IDs from the athing rows (used for comment links)
    item_ids = re.findall(r'class="athing submission" id="(\d+)"', content)

    # Parse subtext: score, user, age, comments, comment item ID
    subtexts = re.findall(
        r'class="subline">.*?'
        r'<span class="score"[^>]*>(\d+) points?</span>'
        r'.*?class="hnuser">([^<]+)</a>'
        r'.*?class="age"[^>]*><a[^>]*>([^<]+)</a>'
        r'.*?<a href="item\?id=(\d+)">([^<]+?)(?:&nbsp;)?(?:comments?|discuss)</a>',
        content,
        flags=re.DOTALL,
    )

    stories = []
    for i, (url, raw_title) in enumerate(titles_urls[:30]):
        title = html_module.unescape(raw_title)
        domain_m = re.search(r"https?://(?:www\.)?([^/?#]+)", url)
        domain = domain_m.group(1) if domain_m else ""

        if i < len(subtexts):
            pts, user, age, item_id, cmts = subtexts[i]
            cmts = cmts.strip().replace("\xa0", "")
        else:
            # Fall back to item_ids list if subtext regex missed it
            item_id = item_ids[i] if i < len(item_ids) else ""
            pts, user, age, cmts = "1", "hnuser", "recently", "discuss"

        stories.append({
            "title":    title,   # raw title; John-ification applied later
            "url":      url,
            "domain":   domain,
            "points":   pts,
            "user":     user,
            "age":      age,
            "comments": cmts,
            "item_id":  item_id,
        })

    return stories


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
CSS = r"""
body  { font-family:Verdana, Geneva, sans-serif; font-size:10pt; color:#828282; }
td    { font-family:Verdana, Geneva, sans-serif; font-size:10pt; color:#828282; }
.admin td   { font-family:Verdana, Geneva, sans-serif; font-size:8.5pt; color:#000000; }
.subtext td { font-family:Verdana, Geneva, sans-serif; font-size:7pt; color:#828282; }
input    { font-family:monospace; font-size:10pt; }
input[type='submit'] { font-family:Verdana, Geneva, sans-serif; }
textarea { font-family:monospace; font-size:10pt; resize:both; }
a:link    { color:#000000; text-decoration:none; }
a:visited { color:#828282; text-decoration:none; }
.default { font-family:Verdana, Geneva, sans-serif; font-size:10pt; color:#828282; }
.title   { font-family:Verdana, Geneva, sans-serif; font-size:10pt; color:#828282; overflow:hidden; }
.subtext { font-family:Verdana, Geneva, sans-serif; font-size:7pt; color:#828282; }
.yclinks { font-family:Verdana, Geneva, sans-serif; font-size:8pt; color:#828282; }
.pagetop { font-family:Verdana, Geneva, sans-serif; font-size:10pt; color:#222222; line-height:12px; }
.comhead { font-family:Verdana, Geneva, sans-serif; font-size:8pt; color:#828282; }
.hnname  { margin-left:1px; margin-right:5px; }
#hnmain  { min-width:796px; }
.title a { word-break:break-word; }
.noshow  { display:none; }
.nosee   { visibility:hidden; pointer-events:none; cursor:default; }
.pagetop a:visited { color:#000000; }
.topsel a:link, .topsel a:visited { color:#ffffff; }
.subtext a:link, .subtext a:visited { color:#828282; }
.subtext a:hover { text-decoration:underline; }
.hnmore a:link, a:visited { color:#828282; }
.hnmore { text-decoration:underline; }
pre { overflow:auto; padding:2px; white-space:pre-wrap; overflow-wrap:anywhere; }
.votearrow {
  width:10px; height:10px; border:0px; margin:3px 2px 6px;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10'%3E%3Cpolygon points='5,0 10,10 0,10' fill='%23828282'/%3E%3C/svg%3E"),
    linear-gradient(transparent,transparent) no-repeat;
  background-size:10px;
}
.rotate180 {
  -webkit-transform:rotate(180deg); -moz-transform:rotate(180deg);
  -o-transform:rotate(180deg); -ms-transform:rotate(180deg); transform:rotate(180deg);
}
@media only screen and (min-width:300px) and (max-width:750px) {
  #hnmain { width:100%; min-width:0; }
  body { padding:0; margin:0; width:100%; }
  td { height:inherit !important; }
  .title, .comment { font-size:inherit; }
  span.pagetop { display:block; margin:3px 5px; font-size:12px; line-height:normal; }
  span.pagetop b { display:block; font-size:15px; }
  .votearrow { transform:scale(1.3,1.3); margin-right:6px; }
  .votelinks { min-width:18px; }
  .votelinks a { display:block; margin-bottom:9px; }
  input[type='text'], input[type='number'], textarea { font-size:16px; width:90%; }
  .title { font-size:11pt; line-height:14pt; }
  .subtext { font-size:9pt; }
}
.comment { max-width:1215px; overflow-wrap:anywhere; }
"""

LOGO_SVG = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 18 18'%3E"
    "%3Crect width='18' height='18' fill='%23ff6600'/%3E"
    "%3Ctext x='9' y='14' font-family='Verdana' font-size='13' font-weight='bold' "
    "fill='white' text-anchor='middle'%3EJ%3C/text%3E%3C/svg%3E"
)


def render_story(i, s):
    sitebit = (
        f'<span class="sitebit comhead"> '
        f'(<a href="#"><span class="sitestr">{s["domain"]}</span></a>)</span>'
        if s["domain"] else ""
    )
    return (
        f'<tr class="athing submission" id="{i}">'
        f'<td align="right" valign="top" class="title"><span class="rank">{i}.</span></td>'
        f'<td valign="top" class="votelinks"><center>'
        f'<a href="#"><div class="votearrow" title="upvote"></div></a>'
        f'</center></td>'
        f'<td class="title"><span class="titleline">'
        f'<a href="{s["url"]}">{s["title"]}</a>{sitebit}'
        f'</span></td></tr>\n'
        f'<tr><td colspan="2"></td>'
        f'<td class="subtext"><span class="subline">'
        f'<span class="score">{s["points"]} points</span> '
        f'by <a href="#" class="hnuser">{s["user"]}</a> '
        f'<span class="age"><a href="#">{s["age"]}</a></span> '
        f'| <a href="#">hide</a> | '
        f'<a href="https://news.ycombinator.com/item?id={s["item_id"]}">{s["comments"]}&nbsp;comments</a>'
        f'</span></td></tr>\n'
        f'<tr class="spacer" style="height:5px"></tr>'
    )


def build_html(stories):
    story_rows = "\n".join(render_story(i + 1, s) for i, s in enumerate(stories))

    return f"""<html lang="en" op="news"><head>
<meta name="referrer" content="origin">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>John News</title>
<style>{CSS}</style>
</head><body><center>
<table id="hnmain" border="0" cellpadding="0" cellspacing="0" width="85%" bgcolor="#f6f6ef">
<tr><td bgcolor="#ff6600">
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="padding:2px"><tr>
    <td style="width:18px;padding-right:4px">
      <a href="#"><img src="{LOGO_SVG}" width="18" height="18" style="border:1px white solid;display:block"></a>
    </td>
    <td style="line-height:12pt;height:10px;">
      <span class="pagetop">
        <b class="hnname"><a href="#">John News</a></b>
        <a href="#">new</a> | <a href="#">past</a> | <a href="#">comments</a> |
        <a href="#">ask</a> | <a href="#">show</a> | <a href="#">fanmail</a> |
        <a href="#">submit</a>
      </span>
    </td>
    <td style="text-align:right;padding-right:4px;">
      <span class="pagetop"><a href="#">login</a></span>
    </td>
  </tr></table>
</td></tr>
<tr style="height:10px"/>
<tr id="bigbox"><td>
  <table border="0" cellpadding="0" cellspacing="0">
{story_rows}
<tr class="morespace" style="height:10px"></tr>
<tr><td colspan="2"></td><td class="title">
  <a href="#" class="morelink" rel="next">More</a>
</td></tr>
  </table>
</td></tr>
<tr><td>
  <img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" height="10" width="0">
  <table width="100%" cellspacing="0" cellpadding="1"><tr><td bgcolor="#ff6600"></td></tr></table>
  <br>
  <center>
    <a href="#">Consider applying to be a John Mentee! Applications open till you work up the courage.</a>
  </center><br>
  <center>
    <span class="yclinks">
      <a href="#">Guidelines</a> | <a href="#">FAQ</a> | <a href="#">Lists</a> |
      <a href="#">API</a> | <a href="#">Security</a> | <a href="#">Legal</a> |
      <a href="#">Join John's Fan Club</a> | <a href="#">Contact</a>
    </span><br><br>
    <form method="get" action="#">
      <label>Search: <input type="text" name="q" size="17" autocorrect="off"
        spellcheck="false" autocapitalize="off" autocomplete="off"></label>
    </form>
  </center>
</td></tr>
</table></center>
</body></html>
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "index.html"

    print("Fetching HN front page...")
    stories = fetch_hn_stories()
    print(f"  Got {len(stories)} stories.")

    # Ask Claude to write custom John-ifications for all headlines at once
    raw_titles = [s["title"] for s in stories]
    print("Asking Claude to John-ify headlines...")
    john_titles = claude_john_ify(raw_titles)

    if john_titles:
        print("  Claude returned custom headlines.")
        for s, t in zip(stories, john_titles):
            s["title"] = t
    else:
        print("  Using fallback suffixes.")
        for i, s in enumerate(stories):
            s["title"] = fallback_john_ify(s["title"], i)

    html = build_html(stories)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written to {out}")
