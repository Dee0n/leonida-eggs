INSERT INTO counts (poll,opt,n) VALUES ('best-gta',0,1),('best-gta',2,2),('best-gta',5,4),('site',0,3),('site',2,1) ON CONFLICT(poll,opt) DO UPDATE SET n=excluded.n;
