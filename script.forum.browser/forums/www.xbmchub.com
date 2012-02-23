# Parsing data for www.xbmchub.com
import:www.xbmc4xbox.org
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