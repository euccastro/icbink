(print (boolean? (string? (string-append "Hellow" " world!"))))
(print (boolean?))
(print (boolean? #t #f))
(print (boolean? "heh" #t))
(print (boolean? #t "heh"))
(print (equal? #t #t))
(print (equal? "heh" "heh"))
(print (equal? "heh" "non-heh"))
(print (cons "a" "b"))
(print (cons "a" (cons "b" ())))
(print (cons "a" (cons (cons "b" "c") ())))
($define! x "huh")
(print x)
($define! (x (y) z) (cons "xx" (cons (cons "yy" ()) (cons "zz" ()))))
(print x)
(print y)
(print z)
($define! (a (b c) d . e)
  (cons "a"
        (cons (cons "b" (cons "c" ()))
              (cons "d" 
                    (cons "e" (cons "f" ()))))))
(print a)
(print b)
(print c)
(print d)
(print e)

($define! x (list "a" "b" "c" "d" "e"))
(print (cdddr x))


($define! dneppa-gnirts
  ($lambda (a b)
    (print a)
    (print b)
    (string-append b a)))

(print (dneppa-gnirts " mundo " "hola"))

; Missing some primitive to capture current environment.
;(print (eval (cons string-append (cons "a" (cons "b" ())))))
