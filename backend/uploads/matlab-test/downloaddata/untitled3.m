% FrameTime的size为1,n
% R的size为1,m
% VIS01_INT的size为m,n
% VIS01_TI的size为m,n
% VIS01_TI_ERR的size为m,n
% VIS01_VT的size为m,n
% VIS01_VT_ERR的size为m,n

%数据存储
shot=20843;  % shot为跑号 整型数据
ftpobj=ftp('192.168.20.13','exluser','Qweqwe123');
pexist=0;
cd(ftpobj,"HCN"); % HCN为诊断类型
plist=dir(ftpobj);
psize=size(plist);
psize=psize(1);
for i = 1:psize
    if plist(i).name==num2str((fix(shot/1000)+1)*1000,'%05d')
        pexist=1;
    end
end
if ~pexist
    mkdir(ftpobj,num2str((fix(shot/1000)+1)*1000,'%05d'));
end
cd(ftpobj,num2str((fix(shot/1000)+1)*1000,'%05d'));
localpath='C:\Users\wangwei\Desktop';      %'C:\Users\wangwei\Desktop\为指定名称保存在本地，路径可自定义
save([localpath,'\HCN_',num2str(shot,'%05d'),'.mat'],'HCN_NE003','time');            
mput(ftpobj,[localpath,'HCN_',num2str(shot,'%05d'),'.mat']);
close(ftpobj);

%数据上传udp
u1=udp('192.168.20.255','RemotePort',12601);

fopen(u1);

fprintf(u1,['+HCN_',num2str(shot,'%05d')]);%shot为炮号
fclose(u1);

delete(u1);

clear u1;