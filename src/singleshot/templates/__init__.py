
#
# Provide access to the templates to the initweb script
#

#
# Temporary hack, just define all the default templates in here because
#   it turns out it's annoyingly complicated to include data files with
#   python packages distributed with Python 2.3's distutils.
#

def all_templates():
    return __templates.items()
    mydir, myname = os.path.split(__file__)

__templates = {'404.html' : """<html><head><title>Not Found</title></head><body><h1>Not found</h1></body></html>""",

'macros.html' : """<macros>
<div metal:define-macro="paginator" tal:define="p paginator" 
     class="paginator">
<div tal:condition="python:path('paginator/pages') &gt; 1">
<span class="info"><span tal:content="p/pageno">1</span> of <span
tal:content="p/pages">1</span>
(<span tal:content="p/count">1</span> item<span tal:omit-tag="" tal:condition="python:path('p/count') != 1">s</span>)</span>
<ul class="pagelist">
  <li tal:repeat="page p/pageitems"><span class="currentpage" tal:omit-tag="not:page/current"><a tal:attributes="href page/href" tal:omit-tag="not:page/href" tal:content="page/name">1</a></span></li>
</ul>
</div>
</div>
<html xmlns:tal="http://xml.zope.org/namespaces/tal"  
      xmlns:metal="http://xml.zope.org/namespaces/metal"
      metal:define-macro="page">
  <head>
    <title><span tal:content="title" tal:omit-tag="">Page Title</span></title>
    <link rel="alternate" type="application/rss+xml" title="RSS 2.0
	 recent photos" tal:attributes="href ssroot/rss/recent/" />
<style>
.header a { text-decoration: none; }
body {  padding: 5px;  font-family: 'Lucida Grande', Verdana, Arial, Sans-Serif;  text-align: center; }
.textblock {  text-align: left;  font-family: Georgia, serif; margin-left: 4em;  margin-right: 4em; }
.error {  border: 3px solid red;  margin: 10px;  padding: 5px; }
.photo { border: 5px solid black; margin: 15px; }
.thumbnail { border: 2px solid black; margin: 5px; }
#header { height: 50px; padding: 5px; font-size: 15px; margin-bottom: 10px; }
#footer {  margin-top: 40px;  border-top: 1px dotted #888888;  font-size: .7em;  color: #333333; }
.itemcrumbs {   text-align: left;   font-size: .8em;   padding-bottom: 5px; }
.headerimg { float: left; }
.navlinks { display: inline; }
.navlinks li {  display: inline;  padding-right: 10px; }
.paginator {  font-size: .8em;    padding: 8px; }
.paginator .info { font-weight: bold; }
.pagelist {   display: inline; }
.pagelist li {  display: inline;  padding-right: 5px; }
.pagelist li a {  text-decoration: none;  border: solid 1px #dddddd;  padding-left: 3px;  padding-right: 3px;  padding-top: 2px;  padding-bottom: 2px; }
.currentpage a {  color: black;  font-weight: bold; }  
#rsslink {    font-size: 9px;    font-weight: bold;   background-color: #FF6600;    color: #ffffff;    border: 3px solid black;    padding: 3px; }
</style>
   </head>
<body>
<div id="page">
<div id="header">Singleshot: <ul class="navlinks">
<li><a tal:attributes="href ssroot/">Home</a></li>
<li tal:condition="data/keyword"/><a tal:attributes="href ssroot/recent/">recent</a></li>
<li tal:condition="data/keyword"/><a tal:attributes="href ssroot/keyword/">keywords</a></li>
<li tal:condition="data/bydate"/><a tal:attributes="href ssroot/bydate/">by date</a></li>
</ul>
</div>


<div class="itemcrumbs" tal:condition="crumbs">
<div tal:condition="crumbs/parents" class="crumbs">
<span tal:repeat="crumb crumbs/parents"><a href="#"
tal:attributes="href crumb/link" tal:content="crumb/title">Crumb</a> &gt; </span>
<span tal:content="item/title">Item</span>
</div>
</div>


<div id="content"><div metal:define-slot="content">Sample content</div></div>
<div id="footer">Powered by <a href="http://www.singleshot.org/">Singleshot</a>.</div>
</body></html>
</macros>
""",

# --------------------------------------------------------------------

'album.html' : """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns:tal="http://xml.zope.org/namespaces/tal"  
      xmlns:metal="http://xml.zope.org/namespaces/metal"
      metal:use-macro="macros/macros/page">

<div metal:fill-slot="content">
<h2 tal:content="item/title">Album Title</h2>
<div metal:use-macro="macros/macros/paginator" />
<table class="thumbnails" align="center">
  <tr tal:repeat="row itemsbyrows/3">
     <td valign="top" tal:repeat="item row" tal:attributes="class item/cssclassname"><a tal:condition="item/image" href="#"
	  tal:attributes="href item/href;title item/title"><img 
           tal:define="t item/image/sizes/thumb" tal:attributes="src t/href;height t/height;width t/width" class="thumbnail" border="0" /></a><br /><a tal:content="item/title" tal:attributes="href item/href">Item title</a></td></tr></table>       
<div metal:use-macro="macros/macros/paginator" />

</div>
</html>""",

# --------------------------------------------------------------------

'bydate.html' : """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns:tal="http://xml.zope.org/namespaces/tal"  
      xmlns:metal="http://xml.zope.org/namespaces/metal"
      metal:use-macro="macros/macros/page">

<div metal:fill-slot="content">
<div class="textblock">
<h2 tal:content="item/title">Photos by date</h2>
<ul>
  <li tal:repeat="year item/items"><b
  tal:content="year/title">Year</b> (<span tal:content="year/count">count</span>)<ul><li
  tal:repeat="month year/items"><a tal:attributes="href month/href"
  tal:content="month/title">Month</a> (<span tal:content="month/count">count</span>)</li></ul></li>
</ul>
</div></div>
</html>""",

# --------------------------------------------------------------------

'keywords.html' : """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns:tal="http://xml.zope.org/namespaces/tal"  
      xmlns:metal="http://xml.zope.org/namespaces/metal"
      metal:use-macro="macros/macros/page">

<div metal:fill-slot="content">
<h2 tal:content="item/title">Album Title</h2>
<div style="margin: 0px auto; width: 60%">
<table border="0">
  <tr>
     <td valign="top" tal:repeat="row itemsbycolumns/4">
     <div style="text-align:left;" tal:repeat="item row" tal:attributes="class
	  item/cssclassname"><a tal:attributes="href item/href;title item/name"
  tal:content="item/name">tag</a></div></td></tr></table>
 
  <span tal:repeat="tag item/items"> </span>
</div>
</div>

</html>""",

# --------------------------------------------------------------------

'recent.html' : """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns:tal="http://xml.zope.org/namespaces/tal"  
      xmlns:metal="http://xml.zope.org/namespaces/metal"
      metal:use-macro="macros/macros/page">

<div metal:fill-slot="content">
<h2 tal:content="item/title">Album Title</h2>
<table class="thumbnails" align="center">
  <tr tal:repeat="row itemsbyrows/3">
     <td valign="top" tal:repeat="item row" tal:attributes="class item/cssclassname"><a tal:condition="item" href="#"
	  tal:attributes="href item/href;title item/title"><img 
           tal:define="t item/image/sizes/thumb" tal:attributes="src t/href;height t/height;width t/width" class="thumbnail" border="0" /></a></td></tr></table>
       
</div>

</html>""",

# --------------------------------------------------------------------

'rssitem.html' : """<div>
<a tal:attributes="href absoluteitemhref"><img tal:define="t item/sizes/bigthumb" tal:attributes="src t/href;height  t/height;width t/width" style="border: 3px solid black" border="0" /></a>
<div tal:content="item/title" style="font-weight: bold;">Item Title</div>
</div>""",

# --------------------------------------------------------------------

'view.html' : """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns:tal="http://xml.zope.org/namespaces/tal"  
      xmlns:metal="http://xml.zope.org/namespaces/metal"
      metal:use-macro="macros/macros/page">

<div metal:fill-slot="content">

<div class="itemnavigation">

<ul class="navlinks">
<li tal:condition="item/prevItem"><a tal:attributes="href item/prevItem/href">prev</a></li>
<li tal:condition="item/nextItem"><a tal:attributes="href item/nextItem/href">next</a></li>
</ul>
</div>
<div>

<img tal:define="t item/sizes/view" tal:attributes="src t/href;height t/height;width t/width" class="thumbnail" border="0" />

<div class="textblock">
<div tal:content="item/title" style="font-weight: bold;">Item Title</div>

<p tal:content="item/caption" tal:condition="item/caption">Caption</p>

<div>Keywords:
<span tal:repeat="tag item/keywords"><a href="#" tal:attributes="href string:${ssroot}keyword/${tag}" tal:content="tag">Keyword</a> </span> </div>

<span tal:content="item/camera_model">Camera</span> 
<span tal:condition="item/exposure_focal" tal:content="string:${item/exposure_focal}mm">Camera</span> 
<span tal:condition="item/exposure_duration"
      tal:content="string:${item/exposure_duration}s">Exposure</span>
<span tal:condition="item/exposure_aperture" 
      tal:content="item/exposure_aperture">Exposure</span>
<span tal:condition="item/exposure_iso" tal:content="string:ISO ${item/exposure_iso}">Exposure</span>
</div>


</div>
       
</div>

</html>"""

}



