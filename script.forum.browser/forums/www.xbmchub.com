#www.xbmchub.com
#www.xbmchub.com
import:.forum.xbmc.org
url:base=http://www.xbmc4xbox.org/forum/
url:threads=viewforum.php?f=!FORUMID!
url:replies=viewtopic.php?f=!FORUMID!&t=!THREADID!
url:subscriptions=ucp.php?i=main&mode=subscribed
url:login=ucp.php?mode=login
url:page_arg=start
url:newpost=viewtopic.php?f=!FORUMID!&t=!THREADID!
#url:newpost=posting.php?mode=reply&f=!FORUMID!&t=!THREADID!
url:gotonewpost=&p=!POSTID!
# The filters
filter:logo=XBMCSVN.com"><img src="(.*?)"
filter:forums=<tr>.*?(?<!<a)(?:\shref="\./viewforum.php\?).*?f=(?P<forumid>\d+).*?>(?P<title>.*?)</a>.*?<p class="forumdesc">(?P<description>.*?)</p>.*?</tr>
filter:threads=<tr><td class="row1"[^<>].+?><img src="[^<>]+?(?:(?P<sticky>ann)ounce)?_\w+\.gif[^<>]+?width="[^<>]+?" />.+?href="\./viewtopic.php\?[^<>]*?t=(?P<threadid>\d+).*?class="topictitle">(?P<title>.*?)</a>.*?<a href="./memberlist.php.*?>(?P<starter>.*?)</a>.*?<a href="./memberlist.php.*?>(?P<lastposter>.*?)</a>.*?<a href="\./viewtopic.php\?.*?;p=(?P<lastid>\d+).*?</tr>
filter:subscriptions=<tr>.*?href="\./viewtopic.php?.*?f=(?P<forumid>\d+).*?t=(?P<threadid>\d+)">(?P<title>.*?)</a>.*?<a href="./memberlist.php.*?>(?P<lastposter>.*?)</a>.*?<a href="\./viewtopic.php\?.*?;p=(?P<lastid>\d+).*?</tr>
filter:replies=<table class="tablebg" width="100%" cellspacing="1">.*?<tr class="row\d">.*?<td class="spacer" colspan="2" height="1"><img src="images/spacer.gif" alt="" width="1" height="1" /></td></tr></table>
filter:post=<a name="p(?P<postid>\d+)"></a>.*?<b class="postauthor".*?>(?P<user>.*?)</b>.*?Post subject:</b>(?P<title>.*?)</div>.*?(?P<date>\w+\s\w+\s\d+,\s\d+\s\d+:\d+\s\w\w).*?<td class="postdetails">(?P<status>.+?)</td>.+?(?:(?:<img src="(?P<avatar>\./download/file.php\?avatar=.*?)")|(?:,)).*?<div class="postbody" id="postdiv.*?>(?P<message>.*?)<br clear="all" /><br />.*?\?mode=viewprofile&amp;u=
filter:quote=<div class="quotetitle">(?:(?P<user>\w+)+\swrote:)?.*?</div><div class="quotecontent">(?P<quote>.+?)</div>
filter:code=<div class="codetitle"><b>Code:</b></div><div class="codecontent">(?P<code>.+?)</div>
filter:page=>&nbsp;Page\s<strong>(?P<page>\d+)</strong> of <strong>(?P<total>\d+)</strong>
filter:next=&amp;start=(?P<start>\d+)">Next</a>
filter:prev=&amp;start=(?P<start>\d+)">Previous</a>

form:login_action=ucp.php?mode=login&
form:login_user=username
form:login_pass=password

#form:post_name=postform
form:post_action=posting.php
form:post_title=subject
form:post_message=message
form:post_submit_name=post
form:post_submit_value=Submit
form:post_submit_wait=2

theme:window_bg=FF222933
theme:title_bg=FFC1CAD2
theme:title_fg=FF000000
theme:post_code=FF005500

## Formats ####################################
format:quote=[QUOTE=%(user)s;%(postid)s]%(quote)s[/QUOTE]
format:replies_per_page=10
format:threads_per_page=25

url:logo=http://www.xbmchub.com/images/index-logo.png
# The URLs
url:base=http://xbmchub.com/oldforums/
# The filters
filter:logo=<a.*?href="./index.php.*?"><img src="(?P<suburl>.*?)"

filter:forums=(?s)<dt.*?<a href="\./viewforum.php\?f=(?P<forumid>\d+).*?class="forumtitle">(?P<title>.*?)</a>.*?<span class="sn-forum-description">(?P<description>.*?)</span>.*?</dt>

filter:threads=<li class="row bg\d[^"]*?(?P<sticky>icky|unce)?">.*?<a href="\./viewtopic.php\?[^<>]*?t=(?P<threadid>\d+).*?class="topictitle">(?P<title>.*?)</a>.*?<dd class="author">.*?>(?P<starter>.+?)</a>.*?</dd>.*?<dd class="lastpost".*?">(?P<lastposter>[^>]+?)</a>.*?</li>

filter:replies=(?s)<div id="p\d+" class="post bg\d[^"]*?">.*?<hr class="divider" ?/>
filter:post=(?s)<a href="#p(?P<postid>\d+)">(?P<title>.*?)</a>.*?<p class="author">.*?memberlist.php[^>]*?>(?P<user>[^<]*?)<.*?(?P<date>\w+\s\w+\s\d+,\s\d+\s\d+:\d+\s\w\w) <.*?class="content">(?P<message>.*?)<dl class="postprofile.*?">.*?<a href="\./memberlist\.php\?[^"]*?">(?:<img src="(?P<avatar>[^"]*?)" width=")?.*?<dd>(?P<status>.*?)</dd>

filter:quote=<blockquote><div>(?:<cite>(?P<user>\w+)+\swrote:</cite>)?.*?(?P<quote>.+?)</blockquote>

filter:page=Page\s<strong>(?P<page>\d+)</strong> of <strong>(?P<total>\d+)</strong>
filter:next=&amp;start=(?P<start>\d+)"[^>]*?>Next</a>
filter:prev=&amp;start=(?P<start>\d+)"[^>]*?>Previous</a>

format:forums_in_threads=True

theme:window_bg=FFCCCCCC
theme:title_bg=FF0D68AF
theme:title_fg=FFFFFFFF
theme:desc_fg=FF000000
theme:post_code=FF000000