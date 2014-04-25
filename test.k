(println (($vau (x) env (eval x env)) (string-append "hey!" "hou!")))
(println (($vau (x) env x) (string-append "hey!" "hou")))
(println (boolean? (string? (string-append "Hellow" " world!"))))
(println (boolean?))
(println (boolean? #t #f))
(println (boolean? "heh" #t))
(println (boolean? #t "heh"))
(println (equal? #t #t))
(println (equal? "heh" "heh"))
(println (equal? "heh" "non-heh"))
(println (cons "a" "b"))
(println (cons "a" (cons "b" ())))
(println (cons "a" (cons "b" "c")))
(println (cons "a" (cons (cons "b" "c") ())))
($define! x "huh")
(println x)
($define! (x (y) z) (cons "xx" (cons (cons "yy" ()) (cons "zz" ()))))
(println x)
(println y)
(println z)
($define! (a (b c) d . e)
  (cons "a"
        (cons (cons "b" (cons "c" ()))
              (cons "d" 
                    (cons "e" (cons "f" ()))))))
(println a)
(println b)
(println c)
(println d)
(println e)

(($vau () env (println "um") (println "outro")))

($define! x (list "a" "b" "c" "d" "e"))
(println (cdddr x))


($define! dneppa-gnirts
  ($lambda (a b)
    (println a)
    (println b)
    (string-append b a)))

(println (string? "x"))
(println ($cond ((boolean? "x") "1")
              ((string? "x") "success")
              (#f "wut")
              (#t "shouldn't reach here")
              (#f "wat")))

(println (dneppa-gnirts " mundo " "hola"))

(println (not? #t))

(println (($lambda (s) (string-append s "!")) "a"))

(println (list "a" "b" "c"))
(println (list* "a" "b" "c"))
(println (list* "a" "b" (list "c" "d")))

(println (map1 ($lambda (x) x) (list "a" "b" "c")))

(println (map1 ($lambda (s) (string-append s "!")) (list "a" "b" "c")))

($let ((m "heh"))
  (println m))

($let ((a "heheh")
       ((b c d) (list "bee" "cee" "dee")))
  (println (list a b c d)))

($let ((env (($vau () env env))))
  (println (eval (cons string-append (cons "a" (cons "b" ()))) env)))

(println "Testing...")

($define! $test
  ($vau (name expected . body) env
    (println "Testing" name "...")
    ($let ((result (eval (cons $sequence body) env)))
      ($if (equal? result expected)
        #inert
        (test-error name "; expected:" expected
                         ", actual:" result)))))

; XXX: use a keyed variable when we have those.
($define! current-trace ())

($define! test-env (get-current-environment))

($define! get-trace
  ($lambda () (reverse current-trace)))

($define! reset-trace!
  ($lambda () ($set! test-env current-trace ())))

($define! trace
  ($lambda (x) ($set! test-env current-trace (cons x current-trace))))

($define! $trace-and-result
  ($vau (body . envoper) env
    (reset-trace!)
    ($let ((result (eval (cons $sequence body) ($if (null? envoper) env (car envoper)))))
      (list (get-trace) result))))

; Test with trace.
($define! $t/t
  ($vau (name expected-trace expected-result . body) env
    (println "Testing" name "...")
    ($let (((trace result) ((wrap $trace-and-result) body env)))
      ($define! error ())
      ($unless (equal? trace expected-trace)
         ($define! error (list* "wrong trace! expected:" expected-trace 
                                "but got:" trace 
                                error)))
      ($unless (equal? result expected-result)
         ($define! error (list* "wrong result! expected:" expected-result
                                "but got:" result
                                error)))
      ($unless (null? error)
        (apply test-error (list* name error))))))
        
; Tests BEGIN

; Let's begin by testing trace itself.

($test "trace initial state" () (get-trace))
($test "trace something" ("a") (trace "a") (get-trace))
($test "reset trace" () (reset-trace!) (get-trace))
($test "trace order" ("a" "b") (reset-trace!) (trace "a") (trace "b") (get-trace))
($test "$trace-and-result" (("a" "b") "c") ($trace-and-result ((trace "a") (trace "b") "c")))
($t/t "$t/t" ("a" "b") "c" (trace "a") (trace "b") "c")

(println)
(println "All OK.")
