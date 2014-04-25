($define! map1
  ($lambda (fn ls)
     ($if (null? ls)
       ()
       (cons (fn (car ls)) (map1 fn (cdr ls))))))

($define! map
  ($lambda (fn . lists)
    ($if (null? (car lists))
        ()
        (cons (apply fn (map1 car lists))
              (map fn (map1 cdr lists))))))

($define! $let
  ($vau (bindings . body) env
    (eval (cons (list* $lambda (map1 car bindings) body)
                (map1 cadr bindings))
          env)))

($define! not?
  ($lambda (x) ($if x #f #t)))

($define! and?
  ($lambda x
    (cond ((null? x) #t)
          ((car x) (and? (cdr x)))
          (#t #f))))

($define! or?
  ($lambda x
    (cond ((null? x) #f)
          ((car x) #t)
          (#t (or? (cdr x))))))

($define! $and?
  ($vau x e
    (cond ((null? x) #t)
          ((null? (cdr x)) (eval (car x) e))
          ((eval (car x) e) (apply (wrap $and?) (cdr x) e))
          (#t #f))))
     
($define! $or?
  ($vau x e
    (cond ((null? x) #f)
          ((null? (cdr x)) (eval (car x) e))
          ((eval (car x) e) #t)
          (#t (apply (wrap $or?) (cdr x) e)))))
