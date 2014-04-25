(println "He llo!")

#inert

(println "hello")

(println #inert)

($define! $tst
  ($vau (expr expected) env
    ($let ((actual (eval expr env)))
      ($if (equal? expected actual)
        #inert
        "false"))))

(println "$app defined")

($define! par
  ($lambda (x)
    (println x)
    x))

(println "par defined")

(println ($tst (par "heh") "heh"))


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
  ($vau (name expr expected) env
    ($let ((result (eval expr env)))
      ($if (equal? result expected)
        #inert
        (test-error (list name
                          (list "expected" expected)
                          (list "actual" result)))))))

(println "All OK.")
