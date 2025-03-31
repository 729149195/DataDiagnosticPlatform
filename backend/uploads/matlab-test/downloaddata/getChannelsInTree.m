function channelNames = getChannelsInTree(tree,shot)
% machine=getappdata(0,'machine');
channelNames={};
mdsopen(tree,shot);

mds_all= char([]);           % storage of all mds path names below TOP
if strcmp(tree,'pcs_hl2m')
    Level_0= ['\' tree '::TOP']; % Top tree name
    Level_1= ['\' tree '::TOP:PC']; % Top tree name
    Level_2= ['\' tree '::TOP:CC']; % Top tree name
    Level_3= ['\' tree '::TOP:FD']; % Top tree name
    Level_4= ['\' tree '::TOP:LM']; % Top tree name
    Level_5= ['\' tree '::TOP:MG']; % Top tree name
    Level_6= ['\' tree '::TOP:SH']; % Top tree name
    Level_7= ['\' tree '::TOP:IP']; % Top tree name
    Level_8= ['\' tree '::TOP:SY']; % Top tree name
    Level_9= ['\' tree '::TOP:FN']; % Top tree name
    Levels=strvcat(char(Level_0),char(Level_1),char(Level_2),char(Level_3),char(Level_4),char(Level_5),char(Level_6),char(Level_7),char(Level_8),char(Level_9));
else
    Level_0= ['\' tree '::TOP']; % Top tree name
    Level_1=   ['getnci("\' Level_0 '.*","FULLPATH")'];
    Levels=strvcat(char(Level_0),char(mdsvalue(Level_1))); % get variable names from mds
end
for kk=1:size(Levels,1)
    mds_nam=   deblank(Levels(kk,:));
    if strcmp(tree,'powersupply')
        mdscmd=    ['getnci("\' mds_nam '.*","FULLPATH")'];
    else
        mdscmd=    ['getnci("\' mds_nam ':*","FULLPATH")'];
    end
    channelNames=[channelNames;mdsvalue(mdscmd)]; % get variable names from mds
end

%

% channelNames=[mdsvalue('getnci("\\pcs_east::TOP:*","FULLPATH")');mdsvalue('getnci("\\pcs_east::TOP.*:*","FULLPATH")')];



patternname='[^\s\o0]*';
channelNames = regexpi(channelNames, patternname, 'match','once');

patternname='[\w]*$';
channelNames = regexpi(channelNames, patternname, 'match','once');

index=~cellfun(@isempty,channelNames);
channelNames=channelNames(index);
mdsclose;
