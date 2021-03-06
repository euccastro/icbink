($define! $let
  ($vau (bindings . body) env
    (eval (cons (list* $lambda (map car bindings) body)
                (map cadr bindings))
          env)))

($define! not?
  ($lambda (x) ($if x #f #t)))

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

($define! $bindings->environment
  ($vau bindings denv
    (eval (list $let-redirect
                (make-environment)
                bindings
                (list get-current-environment))
          denv)))

($define! guard-dynamic-extent
  (wrap
    ($vau (entry-guards combiner exit-guards) env
      ($let ((local (get-current-environment)))
        ($let/cc bypass
          ($set! local bypass bypass)
          (apply-continuation
            (car ($let/cc cont
                   ($set! local enter-through-bypass
                     (continuation->applicative cont))
                   (list bypass)))
            #inert)))
      ($let/cc cont
        (enter-through-bypass
          (extend-continuation
            (guard-continuation
              (cons (list bypass ($lambda (v . #ignore) v))
                    entry-guards)
              cont
              exit-guards)
            ($lambda #ignore
              (apply combiner () env))))))))

($define! member?
  ($lambda (x xs)
    ($cond ((null? xs) #f)
           ((equal? x (car xs)) #t)
           (#t (member? x (cdr xs))))))

($define! $remote-eval
  ($vau (o e) d
    (eval o (eval e d))))

; Since icbink provides no way to create a cyclic list, all lists are finite.
($define! finite-list? list?)

($define! countable-list? list?)

($define! list-tail
  ($lambda (ls k)
    ($if (>? k 0)
      (list-tail (cdr ls) (- k 1))
      ls)))

($define! list-ref
  ($lambda (ls k)
    (car (list-tail ls k))))
