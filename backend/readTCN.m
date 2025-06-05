function [shotnum,statue]=readTCN()
copyfile \\exl50\EXLCCS\CurrentShotNum\TcnStartEnd.txt  ~/DataDiagnostic/DataDiagnosticPlatform/backend/shotinfo
path='~/DataDiagnostic/DataDiagnosticPlatform/backend/shotinfo/TcnStartEnd.txt';
fileContents = fileread(path);
temp = regexp(fileContents, '[0-9]+', 'match');
letters = regexp(fileContents, '[a-zA-Z]+', 'match');
switch  letters{1}
    case 'CB'
        statue=1;  
        shotnum=str2double((temp{1}));
        % 表示倒计时-60开始
    case 'CE'
        statue=2;  
        shotnum=str2double((temp{1}));
        % 表示放电结束了
end
end
