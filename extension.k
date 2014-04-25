; Functions that are not in the kernel report but that I find useful in
; general.

($define! reverse
  ($lambda (lst)
    ($define! aux
      ($lambda (rest accum)
        ($if (null? rest)
          accum
          (aux (cdr rest) (cons (car rest) accum)))))
    (aux lst ())))

($define! $when
  ($vau (test . body) env
    ($if (eval test env)
        (eval (cons $sequence body) env)
        #inert)
    #inert))

($define! $unless
  ($vau (test . body) env
    ($if (not? (eval test env))
        (eval (cons $sequence body) env)
        #inert)
    #inert))

($define! $dbg
  ($vau exprs env
    (println "dbg:")
    (for-each
      ($lambda (e) (println "   " e ":" (eval e env)))
      exprs)))
