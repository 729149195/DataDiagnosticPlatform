function shotnum=currentshot()
 [~,~,~,info]=downloaddata(3001,'ip','-2:5:0.01',0,0);
 shotnum=info{1}.currentshotNum;
end