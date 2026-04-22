#!/usr/bin/env python3
"""
John News generator.
Fetches current HN front page, John-ifies every headline, and writes index.html.
"""

import re
import html as html_module
import urllib.request
import urllib.error
import sys

# ---------------------------------------------------------------------------
# John-ification templates.
# Applied round-robin by story index so output is deterministic per run.
# ---------------------------------------------------------------------------
SUFFIXES = [
    "— John Already Knew This",
    "— John Predicted This Last Year",
    "— John's Version Is Better",
    "— John Wrote a Better Implementation Over the Weekend",
    "— John Called This Three Years Ago",
    "— John's PR Review Improved It by 40%",
    "— John Was Not Surprised",
    "— John Had Already Solved This",
    "— John's Fork Has Twice the Stars",
    "— John Reviewed This and Found Three More Issues",
    "— John's Explanation Remains the Clearest Ever Written",
    "— John Prototyped This Last Quarter",
    "— John Had Been Saying This for Years",
    "— Nobody Told John — He Just Knew",
    "— John's Implementation Uses 40% Less Memory",
    "— John Suggested This in a Slack Message Two Years Ago",
    "— John Peer-Reviewed This and Improved the Algorithm",
    "— John Benchmarked This Against Himself and Won",
    "— John Closed a Related PR Before Breakfast",
    "— John Nodded Approvingly Upon Reading This",
    "— John Not Only Read This, He Cited Three Errors in the Comments",
    "— John's Mental Model of This Is Better Than the Paper",
    "— John Migrated His Entire Stack Away from This Last Year",
    "— John Filed This Bug in 2021 and Was Told It Was By Design",
    "— John's README on This Topic Has More Stars Than the Repo Itself",
    "— John Demoed a Working Prototype of This at Last Week's Standup",
    "— John Quietly Fixed the Underlying Issue Six Months Ago",
    "— John Read the Spec, Found a Gap, and Submitted a Patch",
    "— John's Architecture Diagram of This Made Two Engineers Cry",
    "— John Agrees, Which Settles the Debate",
]

def john_ify(title, idx):
    """Append a John suffix to a headline."""
    suffix = SUFFIXES[idx % len(SUFFIXES)]
    # Avoid double-punctuation at the end
    clean = title.rstrip(".!?")
    return f"{clean} {suffix}"


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

    # Parse subtext: score, user, age, comments
    subtexts = re.findall(
        r'class="subline">.*?'
        r'<span class="score"[^>]*>(\d+) points?</span>'
        r'.*?class="hnuser">([^<]+)</a>'
        r'.*?class="age"[^>]*><a[^>]*>([^<]+)</a>'
        r'.*?<a href="[^"]+">([^<]+?)(?:&nbsp;)?(?:comments?|discuss)</a>',
        content,
        flags=re.DOTALL,
    )

    stories = []
    for i, (url, raw_title) in enumerate(titles_urls[:30]):
        title = html_module.unescape(raw_title)
        domain_m = re.search(r"https?://(?:www\.)?([^/?#]+)", url)
        domain = domain_m.group(1) if domain_m else ""

        if i < len(subtexts):
            pts, user, age, cmts = subtexts[i]
            cmts = cmts.strip().replace("\xa0", "")
        else:
            pts, user, age, cmts = "1", "hnuser", "recently", "discuss"

        stories.append({
            "title":   john_ify(title, i),
            "url":     url,
            "domain":  domain,
            "points":  pts,
            "user":    user,
            "age":     age,
            "comments": cmts,
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
        f'| <a href="#">hide</a> | <a href="#">{s["comments"]}&nbsp;comments</a>'
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
    print("Fetching HN front page…")
    stories = fetch_hn_stories()
    print(f"  Got {len(stories)} stories.")
    html = build_html(stories)
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Written to {out}")
