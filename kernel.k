($define! $let
  ($vau (bindings . body) env
    (eval (cons (list* $lambda (map car bindings) body)
                (map cadr bindings))
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
    ($cond ((null? x) #f)
           ((null? (cdr x)) (eval (car x) e))
           ((eval (car x) e) #t)
           (#t (apply (wrap $or?) (cdr x) e)))))

($define! get-current-environment
  ($vau () e e))

($define! make-kernel-standard-environment
  ($lambda () (get-current-environment)))

($define! $set!
  ($vau (exp1 formals exp2) env
    (eval (list $define! formals
             (list (unwrap eval) exp2 env))
      (eval exp1 env))))

($define! for-each
  (wrap ($vau x env
          (apply map x env)
          #inert)))

($define! apply-continuation
  ($lambda (c o)
    (apply (continuation->applicative c) o)))

($define! $let/cc
  ($vau (symbol . body) env
    (eval (list call/cc (list* $lambda (list symbol) body))
          env)))

($define! $let*
  ($vau (bindings . body) env
    (eval ($if (null? bindings)
            (list* $let bindings body)
            (list $let
                  (list (car bindings))
                  (list* $let* (cdr bindings) body)))
          env)))

($define! $letrec
  ($vau (bindings . body) env
    (eval (list* $let ()
                 (list $define!
                       (map car bindings)
                       (list* list (map cadr bindings)))
                 body)
          env)))

($define! $provide!
  ($vau (symbols . body) env
    (eval (list $define! symbols
                (list $let ()
                      (list* $sequence body)
                      (list* list symbols)))
          env)))

($define! $import!
  ($vau (exp . symbols) env
    (eval (list $set!
                env
                symbols
                (cons list symbols))
          (eval exp env))))

($define! $let-redirect
  ($vau (exp bindings . body) env
    (eval (list* (eval (list* $lambda (map car bindings) body)
                       (eval exp
                             env))
                 (map cadr bindings))
          env)))
